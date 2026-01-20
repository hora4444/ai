class MyConverter:
    regex = r"\d{1,4}" # 0~9까지 4자리

    def to_python(self, value):
        return int(value)

    def to_url(self, value):
        return str(value)
