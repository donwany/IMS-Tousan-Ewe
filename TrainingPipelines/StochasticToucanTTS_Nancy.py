import time

import wandb

from Architectures.ToucanTTS.StochasticToucanTTS.StochasticToucanTTS import (
    StochasticToucanTTS,
)
from Architectures.ToucanTTS.toucantts_train_loop_arbiter import train_loop
from Utility.corpus_preparation import prepare_tts_corpus
from Utility.path_to_transcript_dicts import *
from Utility.storage_config import MODELS_DIR
from Utility.storage_config import PREPROCESSING_DIR


def run(
    gpu_id, resume_checkpoint, finetune, model_dir, resume, use_wandb, wandb_resume_id
):
    if gpu_id == "cpu":
        device = torch.device("cpu")
    else:
        device = torch.device("cuda")

    print("Preparing")

    if model_dir is not None:
        save_dir = model_dir
    else:
        save_dir = os.path.join(MODELS_DIR, "StochasticToucanTTS_Nancy")
    os.makedirs(save_dir, exist_ok=True)

    train_set = prepare_tts_corpus(
        transcript_dict=build_path_to_transcript_dict_nancy(),
        corpus_dir=os.path.join(PREPROCESSING_DIR, "Nancy"),
        lang="eng",
        save_imgs=False,
    )

    model = StochasticToucanTTS()
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
        datasets=[train_set],
        device=device,
        save_directory=save_dir,
        eval_lang="eng",
        path_to_checkpoint=resume_checkpoint,
        fine_tune=finetune,
        resume=resume,
        lr=0.0002,  # it seems the stochastic predictors need a smaller learning rate
        use_wandb=use_wandb,
    )
    if use_wandb:
        wandb.finish()
