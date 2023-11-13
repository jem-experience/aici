from typing import List, Union, Dict, Any

import torch

from vllm.sampling_params import SamplingParams
from vllm.sequence import SequenceGroupMetadata, SequenceGroup, SequenceStatus
from vllm.core.scheduler import Scheduler, SchedulerOutputs

from .comms import AiciRunner


def install(runner: AiciRunner):
    def initiate_step(
        freed_seq_ids: List[int],
        scheduler_outputs: SchedulerOutputs,
    ):
        runner.flush_logit_bias()

        for f in freed_seq_ids:
            runner.step_free_seq(f)

        max_context_len = 0
        num_gen = 0

        for seq_group in scheduler_outputs.scheduled_seq_groups:
            seqs = seq_group.get_seqs(status=SequenceStatus.RUNNING)
            ff_seqs = [seq for seq in seqs if seq.data.num_pending_ff_tokens > 0]
            is_ff = len(ff_seqs) > 0
            if is_ff:
                assert scheduler_outputs.prompt_run
                seqs = ff_seqs
            elif scheduler_outputs.prompt_run:
                assert len(seqs) == 1
            for seq in seqs:
                id = seq.seq_id
                if seq.data.num_pending_ff_tokens:
                    toks = seq.get_token_ids()
                    max_context_len = max(max_context_len, len(toks))
                    runner.step_add_tokens(
                        id,
                        toks[-seq.data.num_pending_ff_tokens :],
                        clone_id=seq.data.parent_id,
                    )
                    seq.data.parent_id = None
                elif scheduler_outputs.prompt_run:
                    toks = seq.get_token_ids()
                    max_context_len = max(max_context_len, len(toks))
                    runner.step_add_prompt(
                        id,
                        prompt=toks,
                        req_id=seq_group.request_id,
                    )
                else:
                    num_gen += 1
                    out = seq.data.output_token_ids
                    max_context_len = max(max_context_len, seq.get_len())
                    runner.step_add_tokens(id, tokens=[out[-1]], clone_id=seq.data.parent_id)
                    seq.data.parent_id = None

        runner.step_finish(max_context_len)
        if num_gen == 0:
            runner.disable_attn_mask = True

    def apply_dynamic_logit_bias(logits: torch.Tensor):
        bias = (
            torch.from_numpy(runner.recv_logit_bias())
            .to(logits.device)
            .to(logits.dtype)
        )
        logits += bias

    def recv_attention_mask():
        return torch.from_numpy(runner.recv_attention_mask())

    def append_ff_tokens(seq_group: SequenceGroup):
        for seq in seq_group.get_seqs():
            resp = runner.response_by_seq_id(seq.seq_id)
            ff = resp and resp.get("ff_tokens", None)
            if ff:
                # print("FF", seq.seq_id, ff, resp)
                seq.pending_ff_tokens = ff

    SamplingParams.apply_dynamic_logit_bias = apply_dynamic_logit_bias
    SamplingParams.initiate_step = initiate_step
    SamplingParams.append_ff_tokens = append_ff_tokens
    SamplingParams.recv_attention_mask = recv_attention_mask
