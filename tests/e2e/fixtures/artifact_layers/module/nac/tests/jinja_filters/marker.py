# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2026 Daniel Schmidt

"""Jinja filter of the module layer; the bundle's one must win."""


class Filter:
    name = "layer_marker"

    @classmethod
    def filter(cls, value):
        return "module"
