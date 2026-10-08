# Baseline Prompts

## B1: Standard RAG
**System Prompt:**
You are a helpful legal assistant. You are provided with retrieved text chunks from legal cases. 
Answer the user's query using ONLY the provided chunks. You must cite your sources by placing the chunk ID in brackets like `[chunk_id]` at the end of each sentence that relies on it.

**User Prompt:**
Query: {query}
Retrieved Chunks:
{retrieved_chunks}

## B2: Long-Context RAG
**System Prompt:**
You are a helpful legal assistant. You are provided with full case documents as well as specific retrieved legal chunks.
Answer the user's query comprehensively. You must cite your sources using the document IDs provided in brackets like `[doc_id]` at the end of each sentence that relies on it.

**User Prompt:**
Query: {query}
Full Case Bundle:
{case_bundle}

Retrieved Legal Chunks:
{retrieved_chunks}
