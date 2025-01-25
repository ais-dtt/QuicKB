# QuicKB 

<img src="qkb_logo.png" width=175>

Optimized Retrieval Knowledge Base & Embedding Model Finetuning

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)

## Overview

QuicKB takes unstructured text documents and creates retrieval-optimized knowledge bases through a complete pipeline that handles:

- Document Chunking
- Synthetic QnA Training Dataset Generation
- Embedding Model Fine Tuning for Retrieval

## Key Features

### Document Chunking
- Multiple chunking strategies:
  - **RecursiveTokenChunker**: Hierarchical splitting using custom separators
  - **FixedTokenChunker**: Precise token-based chunking
  - **LLMSemanticChunker**: LLM-guided natural break points
  - **KamradtModifiedChunker**: Hybrid semantic-token approach
  - **ClusterSemanticChunker**: Content-aware semantic grouping

Chunking Implementation & Techniques Modified From [*ChromaDB: Evaluating Chunking Strategies for Retrieval*](https://research.trychroma.com/evaluating-chunking)

### Training Data Generation
- Automatic question generation from chunks
- Semantic deduplication of similar questions
- Configurable similarity thresholds
- Parallel processing for speed

### Embedding Optimization
- Fine-tune state-of-the-art embedding models
- Optimized for both accuracy and inference speed
- Matryoshka embedding training (768→64D)
- Built-in evaluation metrics and benchmarking

## Installation

```bash
git clone https://github.com/ALucek/QuicKB.git
cd QuicKB

python -m venv quickb-env
source quickb-env/bin/activate  # Windows: quickb-env\Scripts\activate

pip install -e .
```

## Usage

1. Configure your pipeline in `config.yaml`
2. Run:
```bash
python src/main.py
```

## Configuration Guide

The pipeline is controlled through a single `config.yaml` file. Here's a complete configuration example with all available options:

```yaml
# ------------------------------------------------------------------
# Full Pipeline Example (Chunk → Questions → Train → Upload)
# ------------------------------------------------------------------
path_to_knowledgebase: "./knowledgebase"    # Input directory with .txt files
output_path: "./output/kb.json"            # Processed chunks output

chunker: "RecursiveTokenChunker"           # Chunking strategy
chunker_arguments:                         # Chunker-specific parameters
  chunk_size: 400
  chunk_overlap: 0
  separators: ["\n\n", "\n", ".", "?", "!", " ", ""]

generate_questions: true                   # Enable QnA generation
question_output_path: "./output/train.json" 
deduplication:
  enabled: true
  similarity_threshold: 0.85

train_embedding: true                      # Enable model training
training:
  model_id: "nomic-ai/modernbert-embed-base"
  output_dir: "./output/model"
  epochs: 4
  learning_rate: 2.0e-5
  matryoshka_dimensions: [768, 512, 256, 128, 64]
  push_to_hub: true
  hub_model_id: "your-username/model-name"

hub_username: "your-username"              # Hugging Face Hub settings
push_to_hub: true
hub_private: false

# =====================================================
# Partial Configurations 
# =====================================================

# --------------------------------------------------
# 1. Chunking Only Configuration
# --------------------------------------------------
# use_existing_chunks: false
# generate_questions: false
# train_embedding: false
# push_to_hub: false

# --------------------------------------------------
# 2. Generate Questions from Existing Chunks
# --------------------------------------------------
# use_existing_chunks: true
# output_path: "./existing_chunks.json"
# generate_questions: true
# train_embedding: false

# --------------------------------------------------
# 3. Training Only (Existing Chunks + Questions)
# --------------------------------------------------
# use_existing_chunks: true
# output_path: "./existing_chunks.json"
# question_output_path: "./existing_questions.json"
# generate_questions: false
# train_embedding: true

# --------------------------------------------------
# 4. Upload Only (Existing Data)
# --------------------------------------------------
# use_existing_chunks: true
# output_path: "./existing_chunks.json"
# question_output_path: "./existing_questions.json"
# generate_questions: false
# train_embedding: false
# push_to_hub: true
```

### Alternative Chunker Configurations

1. **Fixed Token Chunker**
```yaml
chunker: "FixedTokenChunker"
chunker_arguments:
  encoding_name: "cl100k_base"
  model_name: "text-embedding-3-large"
  chunk_size: 400
  chunk_overlap: 50
```

2. **Cluster Semantic Chunker**
```yaml
chunker: "ClusterSemanticChunker"
chunker_arguments:
  embedding_function: "openai"
  max_chunk_size: 400
  min_chunk_size: 50
```

3. **LLM Semantic Chunker**
```yaml
chunker: "LLMSemanticChunker"
chunker_arguments:
  organisation: "openai"  # or "anthropic"
  model_name: "gpt-4o"
```

4. **Kamradt Modified Chunker**
```yaml
chunker: "KamradtModifiedChunker"
chunker_arguments:
  avg_chunk_size: 400
  min_chunk_size: 50
  embedding_function: "openai"
```

## Output Format

### Knowledgebase Dataset
```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "text": "Section 12.1: Termination clauses...",
  "source": "docs/contracts/2024/Q1-agreement.txt"
}
```

### Training Dataset
```json
{
  "anchor": "What are the termination notice requirements?",
  "positive": "Section 12.1: Either party may terminate...",
  "question_id": "a3b8c7d0-e83a-4b5c-b12d-3f7a8d4c9e1b",
  "chunk_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6"
}
```

## Environment Variables

- `OPENAI_API_KEY`: Required for OpenAI embeddings and question generation
- `HF_TOKEN`: Required for Hugging Face Hub uploads
- `ANTHROPIC_API_KEY`: Optional, required only for Anthropic LLM chunking

## Citations

QuicKB builds upon these foundational works:

ChromaDB: [Evaluating Chunking Strategies for Retrieval](https://research.trychroma.com/evaluating-chunking)
```bibtex
@techreport{smith2024evaluating,
  title = {Evaluating Chunking Strategies for Retrieval},
  author = {Smith, Brandon and Troynikov, Anton},
  year = {2024},
  month = {July},
  institution = {Chroma},
  url = {https://research.trychroma.com/evaluating-chunking},
}
```

Philipp Schmid's [Fine-tune Embedding models for Retrieval Augmented Generation (RAG)](https://www.philschmid.de/fine-tune-embedding-model-for-rag#3-define-loss-function-with-matryoshka-representation)

Sentence Transformers
```bibtext
@inproceedings{reimers-2019-sentence-bert,
  title = "Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks",
  author = "Reimers, Nils and Gurevych, Iryna",
  booktitle = "Proceedings of the 2019 Conference on Empirical Methods in Natural Language Processing",
  month = "11",
  year = "2019",
  publisher = "Association for Computational Linguistics",
  url = "https://arxiv.org/abs/1908.10084",
}
```

## Contributing

Contributions welcome! Please feel free to submit a Pull Request.

Todo List:
- Custom Model Card (Using base from SBERT currently)
- Different Model Support for question generation
- Better handling of intermediate step config logic
- Handle when existing repo for model is in the way
- Update model card for dataset (link to trained model and vice versa)
- Refactoring the trainer for better modular development
- Refactor the steps to their respective sub folders out from main
- python packages for whether ur cpu or gpu
- Readme notes about huggingface

## License

MIT License - See [LICENSE](LICENSE)

