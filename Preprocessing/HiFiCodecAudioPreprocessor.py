import torch
from torchaudio.transforms import Resample

from Preprocessing.Codec.vqvae import VQVAE


class CodecAudioPreprocessor:

    def __init__(
        self,
        input_sr,
        output_sr=16000,
        device="cpu",
        path_to_model="Preprocessing/Codec/HiFi-Codec-16k-320d.pt",
        path_to_config="Preprocessing/Codec/config_16k_320d.json",
    ):
        self.device = device
        self.input_sr = input_sr
        self.output_sr = output_sr
        self.resample = Resample(orig_freq=input_sr, new_freq=output_sr).to(self.device)
        self.model = VQVAE(path_to_config, path_to_model, with_encoder=True)
        self.model.generator.remove_weight_norm()
        self.model.eval()
        self.model.to(device)

    def resample_audio(self, audio, current_sampling_rate):
        if current_sampling_rate != self.input_sr:
            print(
                "warning, change in sampling rate detected. If this happens too often, consider re-ordering the audios so that the sampling rate stays constant for multiple samples"
            )
            self.resample = Resample(
                orig_freq=current_sampling_rate, new_freq=self.output_sr
            ).to(self.device)
            self.input_sr = current_sampling_rate
        if type(audio) != torch.tensor and type(audio) != torch.Tensor:
            audio = torch.tensor(audio, device=self.device, dtype=torch.float32)
        audio = self.resample(audio.float().to(self.device))
        return audio

    @torch.inference_mode()
    def audio_to_codebook_indexes(self, audio, current_sampling_rate):
        if current_sampling_rate != self.output_sr:
            audio = self.resample_audio(audio, current_sampling_rate)
        elif type(audio) != torch.tensor and type(audio) != torch.Tensor:
            audio = torch.tensor(audio, device=self.device, dtype=torch.float32)
        return (
            self.model.encode(audio.float().unsqueeze(0).to(self.device))
            .squeeze()
            .transpose(0, 1)
        )

    @torch.inference_mode()
    def indexes_to_one_hot(self, indexes):
        return torch.nn.functional.one_hot(
            indexes.squeeze(), num_classes=self.model.quantizer.h.n_codes
        )

    @torch.inference_mode()
    def audio_to_one_hot_indexes(self, audio, current_sampling_rate):
        indexes = self.audio_to_codebook_indexes(
            audio=audio, current_sampling_rate=current_sampling_rate
        )
        return self.indexes_to_one_hot(indexes=indexes)

    @torch.inference_mode()
    def indexes_to_codec_frames(self, codebook_indexes):
        if len(codebook_indexes.size()) == 2:
            codebook_indexes = codebook_indexes.unsqueeze(0)
        return self.model.quantizer.embed(codebook_indexes.transpose(1, 2)).squeeze()

    @torch.inference_mode()
    def audio_to_codec_tensor(self, audio, current_sampling_rate):
        indexes = self.audio_to_codebook_indexes(
            audio=audio, current_sampling_rate=current_sampling_rate
        )
        return self.indexes_to_codec_frames(codebook_indexes=indexes)

    @torch.inference_mode()
    def indexes_to_audio(self, codebook_indexes):
        return self.codes_to_audio(self.indexes_to_codec_frames(codebook_indexes))

    @torch.inference_mode()
    def codes_to_audio(self, continuous_codes):
        return self.model.generator(continuous_codes).squeeze()


if __name__ == "__main__":
    import soundfile

    import time

    with torch.inference_mode():
        test_audio1 = "../audios/ad01_0000.wav"
        test_audio2 = "../audios/angry.wav"
        test_audio3 = "../audios/ry.wav"
        test_audio4 = "../audios/test.wav"
        ap = CodecAudioPreprocessor(
            input_sr=1,
            path_to_model="Codec/HiFi-Codec-16k-320d.pt",
            path_to_config="Codec/config_24k_320d.json",
        )

        wav, sr = soundfile.read(test_audio1)
        indexes_1 = ap.audio_to_codebook_indexes(wav, current_sampling_rate=sr)
        wav, sr = soundfile.read(test_audio2)
        indexes_2 = ap.audio_to_codebook_indexes(wav, current_sampling_rate=sr)
        wav, sr = soundfile.read(test_audio3)
        indexes_3 = ap.audio_to_codebook_indexes(wav, current_sampling_rate=sr)
        wav, sr = soundfile.read(test_audio4)
        indexes_4 = ap.audio_to_codebook_indexes(wav, current_sampling_rate=sr)

        t0 = time.time()

        audio1 = ap.indexes_to_audio(indexes_1)
        audio2 = ap.indexes_to_audio(indexes_2)
        audio3 = ap.indexes_to_audio(indexes_3)
        audio4 = ap.indexes_to_audio(indexes_4)

        t1 = time.time()

        print(audio1.shape)
        print(audio2.shape)
        print(audio3.shape)
        print(audio4.shape)

        print(t1 - t0)
        soundfile.write(
            file=f"../audios/1_reconstructed_in_{t1 - t0}_hifi.wav",
            data=audio1,
            samplerate=16000,
        )
        soundfile.write(
            file=f"../audios/2_reconstructed_in_{t1 - t0}_hifi.wav",
            data=audio2,
            samplerate=16000,
        )
        soundfile.write(
            file=f"../audios/3_reconstructed_in_{t1 - t0}_hifi.wav",
            data=audio3,
            samplerate=16000,
        )
        soundfile.write(
            file=f"../audios/4_reconstructed_in_{t1 - t0}_hifi.wav",
            data=audio4,
            samplerate=16000,
        )
