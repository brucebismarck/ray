from typing import List

from ray.rllib.algorithms.appo.appo import OLD_ACTION_DIST_LOGITS_KEY
from ray.rllib.algorithms.appo.appo_rl_module import APPORLModule
from ray.rllib.algorithms.ppo.tf.ppo_tf_rl_module import PPOTfRLModule
from ray.rllib.core.columns import Columns
from ray.rllib.core.models.base import ACTOR
from ray.rllib.core.models.tf.encoder import ENCODER_OUT
from ray.rllib.core.rl_module.rl_module_with_target_networks_interface import (
    RLModuleWithTargetNetworksInterface,
)
from ray.rllib.utils.annotations import override
from ray.rllib.utils.framework import try_import_tf
from ray.rllib.utils.nested_dict import NestedDict

_, tf, _ = try_import_tf()


class APPOTfRLModule(PPOTfRLModule, APPORLModule):
    @override(PPOTfRLModule)
    def setup(self):
        super().setup()

        # If the module is not for inference only, set up the target networks.
        if not self.config.inference_only:
            self.old_pi.set_weights(self.pi.get_weights())
            self.old_encoder.set_weights(self.encoder.get_weights())
            self.old_pi.trainable = False
            self.old_encoder.trainable = False

    @override(RLModuleWithTargetNetworksInterface)
    def sync_target_networks(self, tau: float) -> None:
        for target_network, current_network in [
            (self.old_pi, self.pi),
            (self.old_encoder, self.encoder),
        ]:
            for old_var, current_var in zip(
                target_network.variables, current_network.variables
            ):
                updated_var = tau * current_var + (1.0 - tau) * old_var
                old_var.assign(updated_var)

    @override(PPOTfRLModule)
    def output_specs_train(self) -> List[str]:
        return [
            Columns.ACTION_DIST_INPUTS,
            Columns.VF_PREDS,
            OLD_ACTION_DIST_LOGITS_KEY,
        ]

    @override(PPOTfRLModule)
    def _forward_train(self, batch: NestedDict):
        outs = super()._forward_train(batch)
        batch = batch.copy()
        old_pi_inputs_encoded = self.old_encoder(batch)[ENCODER_OUT][ACTOR]
        old_action_dist_logits = tf.stop_gradient(self.old_pi(old_pi_inputs_encoded))
        outs[OLD_ACTION_DIST_LOGITS_KEY] = old_action_dist_logits
        return outs
