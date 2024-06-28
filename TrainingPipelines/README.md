This directory contains all the pipelines, which are called in the run_training_pipeline.py script. A pipeline is a wrapper around the train loop, that loads a dataset and sets hyperparameters and settings, which it then all forwards into the actual train loop of the corresponding task. Since the TTS train loops have an arbiter that
decides whether the mono-lingual or the multi-lingual train loop will be run, this does not need to be decided in the pipeline. All datasets that belong to the same language should be combined into a concat dataset before being passed to the train loop function for the arbiter to work correctly.