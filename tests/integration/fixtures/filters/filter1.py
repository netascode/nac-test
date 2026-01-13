# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt


class Filter:
    name = "filter1"

    @classmethod
    def filter(cls, data: str) -> str:
        return str(data) + "_filtered"
