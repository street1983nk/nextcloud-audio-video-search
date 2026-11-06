"""The schema of the segment index.

One document per transcript segment of one index revision of a media item. The
four keys are unsigned fast fields: indexed because deletion goes through a term
query on them, fast because the search reads them for every hit, stored so a
document can be read on its own.

The text goes through all three chains. Only body_de is stored; the excerpt is
cut from it, and a second copy would double the document store. Phase 1 writes
the same segment text into all three fields; the language choice per segment
comes in phases 3 and 7.

Changing a line here raises SCHEMA_VERSION: the schema is written into the index
directory once, so a change means a new directory built from SQLite.
"""

from typing import Final

from tantivy import Schema, SchemaBuilder

from audio_video_search_backend.index.analyzer import TOKENIZER_DE, TOKENIZER_EN, TOKENIZER_FR

SCHEMA_VERSION: Final = 1

FIELD_MEDIA_ID: Final = "media_id"
FIELD_INDEX_REV: Final = "index_rev"
FIELD_SEG_IDX: Final = "seg_idx"
FIELD_START_MS: Final = "start_ms"
FIELD_BODY_DE: Final = "body_de"
FIELD_BODY_EN: Final = "body_en"
FIELD_BODY_FR: Final = "body_fr"
BODY_FIELDS: Final = (FIELD_BODY_DE, FIELD_BODY_EN, FIELD_BODY_FR)


def build_schema() -> Schema:
    """The schema of a new index directory; read back from the directory afterwards."""
    builder = SchemaBuilder()
    for field in (FIELD_MEDIA_ID, FIELD_INDEX_REV, FIELD_SEG_IDX, FIELD_START_MS):
        builder.add_unsigned_field(field, stored=True, indexed=True, fast=True)
    builder.add_text_field(FIELD_BODY_DE, stored=True, tokenizer_name=TOKENIZER_DE)
    builder.add_text_field(FIELD_BODY_EN, stored=False, tokenizer_name=TOKENIZER_EN)
    builder.add_text_field(FIELD_BODY_FR, stored=False, tokenizer_name=TOKENIZER_FR)
    return builder.build()
