"""
Example script for fine-tuning the pretrained model to your own data.

Comments in ALL CAPS are instructions
"""

import time

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
    if gpu_id == "cpu":
        device = torch.device("cpu")
    else:
        device = torch.device("cuda")
    assert gpu_count == 1  # distributed finetuning is not supported

    # IF YOU'RE ADDING A NEW LANGUAGE, YOU MIGHT NEED TO ADD HANDLING FOR IT IN Preprocessing/TextFrontend.py

    print("Preparing")

    if model_dir is not None:
        save_dir = model_dir
    else:
        save_dir = os.path.join(
            MODELS_DIR, "ToucanTTS_German_and_English"
        )  # RENAME TO SOMETHING MEANINGFUL FOR YOUR DATA
    os.makedirs(save_dir, exist_ok=True)

    all_train_sets = (
        list()
    )  # YOU CAN HAVE MULTIPLE LANGUAGES, OR JUST ONE. JUST MAKE ONE ConcatDataset PER LANGUAGE AND ADD IT TO THE LIST.
    train_samplers = list()

    # =======================
    # =    German Data      =
    # =======================
    german_datasets = list()
    german_datasets.append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_karlsson(),
            corpus_dir=os.path.join(PREPROCESSING_DIR, "Karlsson"),
            lang="deu",
        )
    )  # CHANGE THE TRANSCRIPT DICT, THE NAME OF THE CACHE DIRECTORY AND THE LANGUAGE TO YOUR NEEDS

    german_datasets.append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_eva(),
            corpus_dir=os.path.join(PREPROCESSING_DIR, "Eva"),
            lang="deu",
        )
    )  # YOU CAN SIMPLY ADD MODE CORPORA AND DO THE SAME, BUT YOU DON'T HAVE TO, ONE IS ENOUGH

    all_train_sets.append(ConcatDataset(german_datasets))

    # ========================
    # =    English Data      =
    # ========================
    english_datasets = list()
    english_datasets.append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_nancy(),
            corpus_dir=os.path.join(PREPROCESSING_DIR, "Nancy"),
            lang="eng",
        )
    )

    english_datasets.append(
        prepare_tts_corpus(
            transcript_dict=build_path_to_transcript_dict_ljspeech(),
            corpus_dir=os.path.join(PREPROCESSING_DIR, "LJSpeech"),
            lang="eng",
        )
    )

    all_train_sets.append(ConcatDataset(english_datasets))

    model = ToucanTTS()

    for train_set in all_train_sets:
        train_samplers.append(torch.utils.data.RandomSampler(train_set))

    if use_wandb:
        wandb.init(
            name=(
                f"{__name__.split('.')[-1]}_{time.strftime('%Y%m%d-%H%M%S')}"
                if wandb_resume_id is None
                else None
            ),
            id=wandb_resume_id,  # this is None if not specified in the command line arguments.
            resume="must" if wandb_resume_id is not None else None,
        )

    print("Training model")
    train_loop(
        net=model,
        datasets=all_train_sets,
        device=device,
        save_directory=save_dir,
        batch_size=12,  # YOU MIGHT GET OUT OF MEMORY ISSUES ON SMALL GPUs, IF SO, DECREASE THIS.
        eval_lang="deu",  # THE LANGUAGE YOUR PROGRESS PLOTS WILL BE MADE IN
        warmup_steps=500,
        lr=1e-5,  # if you have enough data (over ~1000 datapoints) you can increase this up to 1e-4 and it will still be stable, but learn quicker.
        # DOWNLOAD THESE INITIALIZATION MODELS FROM THE RELEASE PAGE OF THE GITHUB OR RUN THE DOWNLOADER SCRIPT TO GET THEM AUTOMATICALLY
        path_to_checkpoint=(
            os.path.join(MODELS_DIR, "ToucanTTS_Meta", "best.pt")
            if resume_checkpoint is None
            else resume_checkpoint
        ),
        fine_tune=True if resume_checkpoint is None and not resume else finetune,
        resume=resume,
        steps=5000,
        use_wandb=use_wandb,
        train_samplers=train_samplers,
        gpu_count=1,
    )
    if use_wandb:
        wandb.finish()
