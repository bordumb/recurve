"""A truncation helper that cuts text silently -- no marker at all. To a
reviewer (or a human) reading it, this is indistinguishable from the file
genuinely being incomplete -- exactly the bug found running the real
smoke, where a whole 3497-char probe was excerpted at 3000 chars and its
own truncation was flagged as the file's defect."""


def broken_cap(text: str, max_chars: int) -> str:
    return text[:max_chars]
