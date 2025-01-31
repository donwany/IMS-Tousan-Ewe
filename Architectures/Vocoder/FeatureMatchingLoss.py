# Copyright 2021 Tomoki Hayashi
# MIT License (https://opensource.org/licenses/MIT)
# Adapted by Florian Lux 2021


import torch
import torch.nn.functional as F


def feature_loss(fmap_r, fmap_g):
    loss = 0
    for dr, dg in zip(fmap_r, fmap_g):
        loss += torch.mean(torch.abs(dr - dg))

    return loss / len(fmap_g)


class FeatureMatchLoss(torch.nn.Module):

    def __init__(
        self,
        average_by_layers=True,
        average_by_discriminators=False,
        include_final_outputs=False,
    ):
        super().__init__()
        self.average_by_layers = average_by_layers
        self.average_by_discriminators = average_by_discriminators
        self.include_final_outputs = include_final_outputs

    def forward(self, feats_hat, feats):
        """
        Calculate feature matching loss.

        Args:
            feats_hat (list): List of lists of discriminator outputs
                calculated from generator outputs.
            feats (list): List of lists of discriminator outputs
                calculated from ground-truth.

        Returns:
            Tensor: Feature matching loss value.
        """
        feat_match_loss = 0.0
        for i, (feats_hat_, feats_) in enumerate(zip(feats_hat, feats)):
            feat_match_loss_ = 0.0
            if not self.include_final_outputs:
                feats_hat_ = feats_hat_[:-1]
                feats_ = feats_[:-1]
            for j, (feat_hat_, feat_) in enumerate(zip(feats_hat_, feats_)):
                feat_match_loss_ += F.l1_loss(feat_hat_, feat_.detach())
            if self.average_by_layers:
                feat_match_loss_ /= j + 1
            feat_match_loss += feat_match_loss_
        if self.average_by_discriminators:
            feat_match_loss /= i + 1

        return feat_match_loss
