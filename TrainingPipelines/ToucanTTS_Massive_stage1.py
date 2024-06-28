"""

STAGE 2: Introduce multilinguality, on a small and clean scale first

"""

import time

import torch.multiprocessing
import wandb
from torch.utils.data import ConcatDataset

from Architectures.ToucanTTS.ToucanTTS import ToucanTTS
from Architectures.ToucanTTS.toucantts_train_loop_arbiter import train_loop
from Utility.corpus_preparation import prepare_tts_corpus
from Utility.path_to_transcript_dicts import *
from Utility.storage_config import MODELS_DIR
from Utility.storage_config import PREPROCESSING_DIR


def run(
    gpu_id,
    resume_checkpoint,
    finetune,
    model_dir,
    resume,
    use_wandb,
    wandb_resume_id,
    gpu_count,
):
    # It is not recommended training this yourself or to finetune this, but you can.
    # The recommended use is to download the pretrained model from the GitHub release
    # page and finetune to your desired data

    datasets = list()

    base_dir = os.path.join(
        MODELS_DIR, "ToucanTTS_MassiveDataBigModel_stage1_LESS_all_fixed"
    )
    if model_dir is not None:
        meta_save_dir = model_dir
    else:
        meta_save_dir = base_dir
    os.makedirs(meta_save_dir, exist_ok=True)

    print("Preparing")

    if gpu_count > 1:
        rank = int(os.environ["LOCAL_RANK"])
        torch.cuda.set_device(rank)
        torch.distributed.init_process_group(backend="nccl")
    else:
        rank = 0

    lang_to_datasets = dict()

    # ENGLISH

    lang_to_datasets["eng"] = list()

    lang_to_datasets["eng"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_nancy,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "Nancy"),
            lang="eng",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    chunk_count = 50
    chunks = split_dictionary_into_chunks(
        build_path_to_transcript_dict_mls_english(), split_n=chunk_count
    )
    for index in range(chunk_count):
        lang_to_datasets["eng"].append(
            prepare_tts_corpus(
                transcript_dict=chunks[index],
                corpus_dir=os.path.join(
                    PREPROCESSING_DIR, f"mls_english_chunk_{index}"
                ),
                lang="eng",
                gpu_count=gpu_count,
                rank=rank,
            )
        )

    lang_to_datasets["eng"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_ryanspeech,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "Ryan"),
            lang="eng",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["eng"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_ljspeech,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "LJSpeech"),
            lang="eng",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["eng"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_libritts_all_clean,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "libri_all_clean"),
            lang="eng",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["eng"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_RAVDESS,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "ravdess"),
            lang="eng",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["eng"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_blizzard_2013,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "blizzard2013"),
            lang="eng",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["eng"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_jenny,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "jenny"),
            lang="eng",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    # GERMAN
    lang_to_datasets["deu"] = list()

    lang_to_datasets["deu"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_karlsson,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "Karlsson"),
            lang="deu",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["deu"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_hokus,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "Hokus"),
            lang="deu",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["deu"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_hui_others,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "hui_others"),
            lang="deu",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    chunk_count = 10
    chunks = split_dictionary_into_chunks(
        build_path_to_transcript_dict_mls_german(), split_n=chunk_count
    )
    for index in range(chunk_count):
        lang_to_datasets["deu"].append(
            prepare_tts_corpus(
                transcript_dict=chunks[index],
                corpus_dir=os.path.join(PREPROCESSING_DIR, f"mls_german_chunk_{index}"),
                lang="deu",
                gpu_count=gpu_count,
                rank=rank,
            )
        )

    # FRENCH

    lang_to_datasets["fra"] = list()

    lang_to_datasets["fra"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_blizzard2023_ad_silence_removed,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "ad_e"),
            lang="fra",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["fra"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_blizzard2023_neb_silence_removed,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "neb"),
            lang="fra",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["fra"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_blizzard2023_neb_e_silence_removed,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "neb_e"),
            lang="fra",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["fra"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_mls_french,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "mls_french"),
            lang="fra",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    # SPANISH

    lang_to_datasets["spa"] = list()

    lang_to_datasets["spa"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_mls_spanish,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "mls_spanish"),
            lang="spa",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    lang_to_datasets["spa"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_spanish_blizzard_train,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "spanish_blizzard"),
            lang="spa",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    # CHINESE

    lang_to_datasets["cmn"] = list()

    lang_to_datasets["cmn"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_aishell3,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "aishell3"),
            lang="cmn",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    # POLISH

    lang_to_datasets["pol"] = list()

    lang_to_datasets["pol"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_mls_polish,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "mls_polish"),
            lang="pol",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    # PORTUGUESE

    lang_to_datasets["por"] = list()

    lang_to_datasets["por"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_mls_portuguese,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "mls_porto"),
            lang="por",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    # ITALIAN

    lang_to_datasets["ita"] = list()

    lang_to_datasets["ita"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_mls_italian,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "mls_italian"),
            lang="ita",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    # DUTCH

    lang_to_datasets["nld"] = list()

    lang_to_datasets["nld"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_mls_dutch,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "mls_dutch"),
            lang="nld",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    # VIETNAMESE

    lang_to_datasets["vie"] = list()

    lang_to_datasets["vie"].append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_VIVOS_viet,
            corpus_dir=os.path.join(PREPROCESSING_DIR, "VIVOS_viet"),
            lang="vie",
            gpu_count=gpu_count,
            rank=rank,
        )
    )

    for lang in lang_to_datasets:
        datasets.append(ConcatDataset(lang_to_datasets[lang]))
    re_ordered_datasets = list()
    collection_dataset = list()
    for dataset in datasets:
        if (
            len(dataset) < 1000
        ):  # This language is too small to be a task on its own, so we join it with other tiny languages to make a combined task.
            collection_dataset.append(dataset)
        else:
            re_ordered_datasets.append(dataset)
    if len(collection_dataset) != 0:
        re_ordered_datasets.append(ConcatDataset(collection_dataset))
    print(
        f"\n\nTraining jointly on {len(datasets)} languages in a setup of {len(re_ordered_datasets)} tasks! Good luck!\n\n"
    )
    print(lang_to_datasets.keys())
    print("\n\n")

    model = ToucanTTS()

    train_samplers = list()
    if gpu_count > 1:
        model.to(rank)
        model = torch.nn.parallel.DistributedDataParallel(
            model,
            device_ids=[rank],
            output_device=rank,
            find_unused_parameters=True,
        )
        torch.distributed.barrier()
    for train_set in re_ordered_datasets:
        train_samplers.append(torch.utils.data.RandomSampler(train_set))

    if use_wandb:
        if rank == 0:
            wandb.init(
                name=(
                    f"{__name__.split('.')[-1]}_{time.strftime('%Y%m%d-%H%M%S')}"
                    if wandb_resume_id is None
                    else None
                ),
                id=wandb_resume_id,  # this is None if not specified in the command line arguments.
                resume="must" if wandb_resume_id is not None else None,
            )
    train_loop(
        net=model,
        batch_size=20,
        warmup_steps=8000,
        device=torch.device("cuda"),
        datasets=re_ordered_datasets,
        save_directory=meta_save_dir,
        path_to_checkpoint=resume_checkpoint,
        resume=resume,
        fine_tune=finetune,
        steps=40000,
        steps_per_checkpoint=1000,
        lr=0.001,
        use_wandb=use_wandb,
        train_samplers=train_samplers,
        gpu_count=gpu_count,
        use_less_loss=True,
    )
    if use_wandb:
        wandb.finish()
