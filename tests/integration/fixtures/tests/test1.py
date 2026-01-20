# SPDX-License-Identifier: MPL-2.0
# Copyright (c) 2025 Daniel Schmidt


class Test:
    name = "test1"

    @classmethod
    def test(cls, data1: str, data2: str) -> bool:
        return data1 == data2
