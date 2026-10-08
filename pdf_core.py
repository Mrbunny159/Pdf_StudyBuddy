try:
    import pymupdf as fitz
except ImportError:
    import fitz

class PdfBook:
    def __init__(self, path: str, dpi: int = 150):
        self.doc = fitz.open(path)
        self.dpi = dpi
        self.page_count = len(self.doc)

    def get_pixmap(self, page_index: int):
        return self.doc[page_index].get_pixmap(dpi=self.dpi)

    def words(self, page_index: int):
        return self.doc[page_index].get_text("words")

    def get_context(self, page_index: int, hit_word):
        """Gets all words in the same text block as the clicked word."""
        words = self.words(page_index)
        block_no = hit_word[5] # block_no is the 6th element in the tuple
        
        # Grab all words in the same block and join them into a string
        block_words = [w[4] for w in words if w[5] == block_no]
        return " ".join(block_words)