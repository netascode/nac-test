class Filter:
    name = "filter1"

    @classmethod
    def filter(cls, data: str) -> str:
        return str(data) + "_filtered"
