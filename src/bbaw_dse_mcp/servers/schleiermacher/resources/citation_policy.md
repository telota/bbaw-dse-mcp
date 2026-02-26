# Citation Policy for Schleiermacher Digital

## CRITICAL: Preventing Hallucinated Citations

When analyzing documents from the Schleiermacher Digital edition, you MUST follow these rules:

### Rule 1: Only Cite Returned Documents

**NEVER** invent or guess document IDs, brief numbers, or URLs.

- ✅ CORRECT: Use document_id from search results verbatim
- ❌ WRONG: Generate IDs like "Brief 5255" or "s_4986" without seeing them in results

### Rule 2: Use Provided Citation URLs

Each document result includes a `citation_url` field:

```json
{
  "document_id": "S0006428",
  "title": "Brief von Charlotte Schleiermacher",
  "citation_url": "https://schleiermacher-digital.de/S0006428"
}
```

**Document ID Format:** Always capital 'S' + 7 digits (e.g., S0006428, S0007791)
**URL Format:** `https://schleiermacher-digital.de/{document_id}`

When citing, use this EXACT URL. Do NOT construct your own.

### Rule 3: Verify Before Citing

If you want to reference a document:

1. Search for it first using `search_by_keyword()` or `search_letters()`
2. Get the document with `get_document(document_id)`
3. Use the returned `document_id` and `citation_url` verbatim

### Rule 4: Be Transparent About Sources

When making claims:

- State which documents you actually retrieved
- Distinguish between:
  - Direct quotes from retrieved documents
  - Interpretations based on retrieved documents
  - General knowledge that might need verification

### Example: Correct Citation Workflow

**❌ WRONG:**

```
"Laut Brief 5255 von Ernst Moritz Arndt an Schleiermacher (1821)..."
```

(Where did "5255" come from? Hallucinated!)

**✅ CORRECT:**

```
1. search_by_keyword(keyword="Arndt Revolution")
2. get_document(document_id="S0012345")  # From search results
3. "Laut dem Brief von August Twesten (1819, S0012345)..."
   URL: https://schleiermacher-digital.de/S0012345
```

### When You Don't Have Documents

If you cannot find a document to support a claim:

- Say: "I could not find this document in the current search results"
- Offer to search for it: "Shall I search for correspondence with Arndt?"
- Do NOT make up document IDs

## Technical Implementation

All tools return structured data with:

- `document_id`: The exact ID to use in citations
- `citation_url`: The canonical URL for this document
- `title`, `date`, etc.: Metadata for context

When a tool returns this data, treat it as the ONLY valid source for citations.
