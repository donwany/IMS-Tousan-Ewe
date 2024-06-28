import os
import statistics

import torch
from torch.utils.data import Dataset
from tqdm import tqdm

from Architectures.Aligner.Aligner import Aligner
from Architectures.Aligner.CodecAlignerDataset import CodecAlignerDataset
from Architectures.ToucanTTS.DurationCalculator import DurationCalculator
from Architectures.ToucanTTS.EnergyCalculator import EnergyCalculator
from Architectures.ToucanTTS.PitchCalculator import Parselmouth
from Preprocessing.AudioPreprocessor import AudioPreprocessor
from Preprocessing.EnCodecAudioPreprocessor import CodecAudioPreprocessor
from Preprocessing.TextFrontend import get_language_id
from Preprocessing.articulatory_features import get_feature_to_index_lookup
from Utility.utils import remove_elements


class TTSDataset(Dataset):

    def __init__(
        self,
        path_to_transcript_dict,
        acoustic_checkpoint_path,
        cache_dir,
        lang,
        loading_processes=os.cpu_count() if os.cpu_count() is not None else 10,
        min_len_in_seconds=1,
        max_len_in_seconds=15,
        device=torch.device("cpu"),
        rebuild_cache=False,
        ctc_selection=True,
        save_imgs=False,
        gpu_count=1,
        rank=0,
        annotate_silences=False,
    ):
        self.cache_dir = cache_dir
        self.device = device
        self.pttd = path_to_transcript_dict
        os.makedirs(cache_dir, exist_ok=True)
        if (
            not os.path.exists(os.path.join(cache_dir, "tts_train_cache.pt"))
            or rebuild_cache
        ):
            self._build_dataset_cache(
                path_to_transcript_dict=path_to_transcript_dict,
                acoustic_checkpoint_path=acoustic_checkpoint_path,
                cache_dir=cache_dir,
                lang=lang,
                loading_processes=loading_processes,
                min_len_in_seconds=min_len_in_seconds,
                max_len_in_seconds=max_len_in_seconds,
                device=device,
                rebuild_cache=rebuild_cache,
                ctc_selection=ctc_selection,
                save_imgs=save_imgs,
                gpu_count=gpu_count,
                rank=rank,
                annotate_silences=annotate_silences,
            )
        self.cache_dir = cache_dir
        self.gpu_count = gpu_count
        self.rank = rank
        self.language_id = get_language_id(lang)
        self.datapoints = torch.load(
            os.path.join(self.cache_dir, "tts_train_cache.pt"), map_location="cpu"
        )
        if self.gpu_count > 1:
            # we only keep a chunk of the dataset in memory to avoid redundancy. Which chunk, we figure out using the rank.
            while len(self.datapoints) % self.gpu_count != 0:
                self.datapoints.pop(
                    -1
                )  # a bit unfortunate, but if you're using multiple GPUs, you probably have a ton of datapoints anyway.
            chunksize = int(len(self.datapoints) / self.gpu_count)
            self.datapoints = self.datapoints[
                chunksize * self.rank : chunksize * (self.rank + 1)
            ]
        print(
            f"Loaded a TTS dataset with {len(self.datapoints)} datapoints from {cache_dir}."
        )

    def _build_dataset_cache(
        self,
        path_to_transcript_dict,
        acoustic_checkpoint_path,
        cache_dir,
        lang,
        loading_processes=os.cpu_count() if os.cpu_count() is not None else 10,
        min_len_in_seconds=1,
        max_len_in_seconds=15,
        device=torch.device("cpu"),
        rebuild_cache=False,
        ctc_selection=True,
        save_imgs=False,
        gpu_count=1,
        rank=0,
        annotate_silences=False,
    ):
        if gpu_count != 1:
            import sys

            print(
                "Please run the feature extraction using only a single GPU. Multi-GPU is only supported for training."
            )
            sys.exit()
        if (
            not os.path.exists(os.path.join(cache_dir, "aligner_train_cache.pt"))
            or rebuild_cache
        ):
            CodecAlignerDataset(
                path_to_transcript_dict=path_to_transcript_dict,
                cache_dir=cache_dir,
                lang=lang,
                loading_processes=loading_processes,
                min_len_in_seconds=min_len_in_seconds,
                max_len_in_seconds=max_len_in_seconds,
                rebuild_cache=rebuild_cache,
                device=device,
            )
        datapoints = torch.load(
            os.path.join(cache_dir, "aligner_train_cache.pt"), map_location="cpu"
        )
        # we use the aligner dataset as basis and augment it to contain the additional information we need for tts.
        self.dataset, _, speaker_embeddings, filepaths = datapoints

        print("... building dataset cache ...")
        self.codec_wrapper = CodecAudioPreprocessor(input_sr=-1, device=device)
        self.spec_extractor_for_features = AudioPreprocessor(
            input_sr=16000, output_sr=16000, device=device
        )
        self.datapoints = list()
        self.ctc_losses = list()

        self.acoustic_model = Aligner()
        self.acoustic_model.load_state_dict(
            torch.load(acoustic_checkpoint_path, map_location="cpu")["asr_model"]
        )
        self.acoustic_model = self.acoustic_model.to(device)

        torch.hub._validate_not_a_forked_repo = (
            lambda a, b, c: True
        )  # torch 1.9 has a bug in the hub loading, this is a workaround
        # careful: assumes 16kHz or 8kHz audio
        silero_model, utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            verbose=False,
        )
        (get_speech_timestamps, save_audio, read_audio, VADIterator, collect_chunks) = (
            utils
        )
        torch.set_grad_enabled(
            True
        )  # finding this issue was very infuriating: silero sets
        # this to false globally during model loading rather than using inference_mode or no_grad
        silero_model = silero_model.to(device)

        # ==========================================
        # actual creation of datapoints starts here
        # ==========================================

        parsel = Parselmouth(fs=16000)
        energy_calc = EnergyCalculator(fs=16000).to(device)
        self.dc = DurationCalculator()
        vis_dir = os.path.join(cache_dir, "duration_vis")
        if save_imgs:
            os.makedirs(os.path.join(vis_dir, "post_clean"), exist_ok=True)
            if annotate_silences:
                os.makedirs(os.path.join(vis_dir, "pre_clean"), exist_ok=True)

        for index in tqdm(range(len(self.dataset))):
            codes = self.dataset[index][1]
            if codes.size()[0] != 24:  # no clue why this is sometimes the case
                codes = codes.transpose(0, 1)
            decoded_wave = self.codec_wrapper.indexes_to_audio(codes.int().to(device))
            decoded_wave_length = torch.LongTensor([len(decoded_wave)])
            features = self.spec_extractor_for_features.audio_to_mel_spec_tensor(
                decoded_wave, explicit_sampling_rate=16000
            )
            feature_lengths = torch.LongTensor([len(features[0])])

            text = self.dataset[index][0]

            if annotate_silences:
                text = self._annotate_silences(
                    text,
                    get_speech_timestamps,
                    index,
                    vis_dir,
                    decoded_wave,
                    device,
                    features,
                    silero_model,
                    save_imgs,
                    decoded_wave_length,
                )
            cached_duration, ctc_loss = self._calculate_durations(
                text, index, os.path.join(vis_dir, "post_clean"), features, save_imgs
            )

            cached_energy = (
                energy_calc(
                    input_waves=torch.tensor(decoded_wave).unsqueeze(0).to(device),
                    input_waves_lengths=decoded_wave_length,
                    feats_lengths=feature_lengths,
                    text=text,
                    durations=cached_duration.unsqueeze(0),
                    durations_lengths=torch.LongTensor([len(cached_duration)]),
                )[0]
                .squeeze(0)
                .cpu()
            )

            cached_pitch = (
                parsel(
                    input_waves=torch.tensor(decoded_wave).unsqueeze(0),
                    input_waves_lengths=decoded_wave_length,
                    feats_lengths=feature_lengths,
                    text=text,
                    durations=cached_duration.unsqueeze(0),
                    durations_lengths=torch.LongTensor([len(cached_duration)]),
                )[0]
                .squeeze(0)
                .cpu()
            )

            self.datapoints.append(
                [
                    text,  # text tensor
                    torch.LongTensor([len(text)]),  # length of text tensor
                    codes,  # codec tensor (in index form)
                    feature_lengths,  # length of spectrogram
                    cached_duration.cpu(),  # duration
                    cached_energy.float(),  # energy
                    cached_pitch.float(),  # pitch
                    speaker_embeddings[index],  # speaker embedding,
                    filepaths[index],  # path to the associated original raw audio file
                ]
            )
            self.ctc_losses.append(ctc_loss)

        # =============================
        # done with datapoint creation
        # =============================

        if (
            ctc_selection and len(self.datapoints) > 300
        ):  # for less than 300 datapoints, we should not throw away anything.
            # now we can filter out some bad datapoints based on the CTC scores we collected
            mean_ctc = sum(self.ctc_losses) / len(self.ctc_losses)
            std_dev = statistics.stdev(self.ctc_losses)
            threshold = mean_ctc + (std_dev * 3.5)
            for index in range(len(self.ctc_losses), 0, -1):
                if self.ctc_losses[index - 1] > threshold:
                    self.datapoints.pop(index - 1)
                    print(
                        f"Removing datapoint {index - 1}, because the CTC loss is 3.5 standard deviations higher than the mean. \n ctc: {round(self.ctc_losses[index - 1], 4)} vs. mean: {round(mean_ctc, 4)}"
                    )

        # save to cache
        if len(self.datapoints) > 0:
            torch.save(self.datapoints, os.path.join(cache_dir, "tts_train_cache.pt"))
        else:
            import sys

            print("No datapoints were prepared! Exiting...")
            sys.exit()
        del self.dataset

    def _annotate_silences(
        self,
        text,
        get_speech_timestamps,
        index,
        vis_dir,
        decoded_wave,
        device,
        features,
        silero_model,
        save_imgs,
        decoded_wave_length,
    ):
        """
        Takes in a text tensor and returns a text tensor with pauses added in all locations, where there are actually pauses in the speech signal. Unfortunately, this tends to make mistakes and not work quite as intended yet. I might revisit it in the future, if I see the need for extremely accurate labels for a small dataset of e.g. special data.
        """
        text_with_pauses = list()
        for phoneme_index, vector in enumerate(text):
            # We add pauses before every word boundary, and later we remove the ones that were added too much
            if vector[get_feature_to_index_lookup()["word-boundary"]] == 1:
                if (
                    text[phoneme_index - 1][get_feature_to_index_lookup()["silence"]]
                    != 1
                ):
                    text_with_pauses.append(
                        [
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            1.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                            0.0,
                        ]
                    )
                text_with_pauses.append(vector.numpy().tolist())
            else:
                text_with_pauses.append(vector.numpy().tolist())
        text = torch.Tensor(text_with_pauses)

        cached_duration, _ = self._calculate_durations(
            text, index, os.path.join(vis_dir, "pre_clean"), features, save_imgs
        )

        cumsum = 0
        potential_silences = list()
        phoneme_indexes_of_silences = list()
        for phoneme_index, phone in enumerate(text):
            if (
                phone[get_feature_to_index_lookup()["silence"]] == 1
                or phone[get_feature_to_index_lookup()["end of sentence"]] == 1
                or phone[get_feature_to_index_lookup()["questionmark"]] == 1
                or phone[get_feature_to_index_lookup()["exclamationmark"]] == 1
                or phone[get_feature_to_index_lookup()["fullstop"]] == 1
            ):
                potential_silences.append(
                    [cumsum, cumsum + cached_duration[phoneme_index]]
                )
                phoneme_indexes_of_silences.append(phoneme_index)
            cumsum = cumsum + cached_duration[phoneme_index]
        with torch.inference_mode():
            speech_timestamps = get_speech_timestamps(
                torch.Tensor(decoded_wave).to(device), silero_model, sampling_rate=16000
            )
        vad_silences = list()
        prev_end = 0
        for speech_segment in speech_timestamps:
            if prev_end != 0:
                vad_silences.append([prev_end, speech_segment["start"]])
            prev_end = speech_segment["end"]
        # at this point we know all the silences and we know the legal silences.
        # We have to transform them both into ratios, so we can compare them.
        # If a silence overlaps with a legal silence, it can stay.
        illegal_silences = list()
        for silence_index, silence in enumerate(potential_silences):
            illegal = True
            start = silence[0] / len(features)
            end = silence[1] / len(features)
            for legal_silence in vad_silences:
                legal_start = legal_silence[0] / decoded_wave_length
                legal_end = legal_silence[1] / decoded_wave_length
                if legal_start < start < legal_end or legal_start < end < legal_end:
                    illegal = False
                    break
            if illegal:
                # If it is an illegal silence, it is marked for removal in the original wave according to ration with real samplingrate.
                illegal_silences.append(phoneme_indexes_of_silences[silence_index])

        text = remove_elements(
            text, illegal_silences
        )  # now we have all the silences where there should be silences and none where there shouldn't be any. We have to run the aligner again with this new information.
        return text

    def _calculate_durations(self, text, index, vis_dir, features, save_imgs):
        # We deal with the word boundaries by having 2 versions of text: with and without word boundaries.
        # We note the index of word boundaries and insert durations of 0 afterwards
        text_without_word_boundaries = list()
        indexes_of_word_boundaries = list()
        for phoneme_index, vector in enumerate(text):
            if vector[get_feature_to_index_lookup()["word-boundary"]] == 0:
                text_without_word_boundaries.append(vector.numpy().tolist())
            else:
                indexes_of_word_boundaries.append(phoneme_index)
        matrix_without_word_boundaries = torch.Tensor(text_without_word_boundaries)

        alignment_path, ctc_loss = self.acoustic_model.inference(
            features=features.transpose(0, 1),
            tokens=matrix_without_word_boundaries.to(self.device),
            save_img_for_debug=(
                os.path.join(vis_dir, f"{index}.png") if save_imgs else None
            ),
            return_ctc=True,
        )

        cached_duration = self.dc(torch.LongTensor(alignment_path), vis=None).cpu()

        for index_of_word_boundary in indexes_of_word_boundaries:
            cached_duration = torch.cat(
                [
                    cached_duration[:index_of_word_boundary],
                    torch.LongTensor(
                        [0]
                    ),  # insert a 0 duration wherever there is a word boundary
                    cached_duration[index_of_word_boundary:],
                ]
            )
        return cached_duration, ctc_loss

    def __getitem__(self, index):
        return (
            self.datapoints[index][0],
            self.datapoints[index][1],
            self.datapoints[index][2],
            self.datapoints[index][3],
            self.datapoints[index][4],
            self.datapoints[index][5],
            self.datapoints[index][6],
            None,
            self.language_id,
            self.datapoints[index][7],
        )

    def __len__(self):
        return len(self.datapoints)

    def remove_samples(self, list_of_samples_to_remove):
        for remove_id in sorted(list_of_samples_to_remove, reverse=True):
            self.datapoints.pop(remove_id)
        torch.save(self.datapoints, os.path.join(self.cache_dir, "tts_train_cache.pt"))
        print("Dataset updated!")
