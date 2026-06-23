#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations
from relation_core_redteam_scenarios import cases


def scenarios():
    # Base suite reuses the first diverse scenarios from the red-team set.
    # The core does not see expected labels; expected is only for evaluation.
    return cases()[:27]
