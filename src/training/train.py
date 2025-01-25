import os
import json
import logging
import torch
import yaml
from pathlib import Path
from typing import Dict, List
from datasets import load_dataset
from sentence_transformers import (
    SentenceTransformer,
    SentenceTransformerModelCardData,
    SentenceTransformerTrainingArguments,
    SentenceTransformerTrainer,
)
from sentence_transformers.losses import MultipleNegativesRankingLoss, MatryoshkaLoss
from sentence_transformers.evaluation import InformationRetrievalEvaluator, SequentialEvaluator
from sentence_transformers.util import cos_sim
from sentence_transformers.training_args import BatchSamplers
from huggingface_hub import login

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)

def load_main_config(config_path_or_obj):
    """Load configuration from path or use provided config object."""
    if isinstance(config_path_or_obj, (str, bytes, os.PathLike)):
        with open(config_path_or_obj, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)
    return config_path_or_obj.model_dump()

def build_evaluation_structures(kb_dataset, test_dataset, kb_id_field="id", kb_text_field="text"):
    corpus = {row[kb_id_field]: row[kb_text_field] for row in kb_dataset}
    queries = {row["id"]: row["anchor"] for row in test_dataset}
    relevant_docs = {}
    for row in test_dataset:
        q_id = row["id"]
        if "global_chunk_id" not in row:
            logger.warning(f"Missing 'global_chunk_id': {row}")
            continue
        if q_id not in relevant_docs:
            relevant_docs[q_id] = []
        relevant_docs[q_id].append(row["global_chunk_id"])
    return corpus, queries, relevant_docs

def run_baseline_eval(model, evaluator, dim_list):
    results = evaluator(model)
    print("\nBefore Training (Baseline) Results")
    print("-" * 85)
    print(f"{'Metric':15} {' '.join([f'{d:>10}d' for d in dim_list])}")
    print("-" * 85)
    metrics = [
        "ndcg@10", "mrr@10", "map@100",
        "accuracy@1", "accuracy@3", "accuracy@5", "accuracy@10",
        "precision@1", "precision@3", "precision@5", "precision@10",
        "recall@1", "recall@3", "recall@5", "recall@10",
    ]
    for metric in metrics:
        row_values = []
        for dim in dim_list:
            key = f"dim_{dim}_cosine_{metric}"
            val = results[key]
            row_values.append(val)
        print(f"{metric:15}", end="  ")
        for val in row_values:
            print(f"{val:10.4f}", end=" ")
        print()
    print("-" * 85)
    print(f"sequential_score: {results['sequential_score']:.4f}\n")
    return results

def run_final_eval(model, evaluator, dim_list):
    results = evaluator(model)
    print("\nAfter Training (Fine-Tuned) Results")
    print("-" * 85)
    print(f"{'Metric':15} {' '.join([f'{d:>10}d' for d in dim_list])}")
    print("-" * 85)
    metrics = [
        "ndcg@10", "mrr@10", "map@100",
        "accuracy@1", "accuracy@3", "accuracy@5", "accuracy@10",
        "precision@1", "precision@3", "precision@5", "precision@10",
        "recall@1", "recall@3", "recall@5", "recall@10",
    ]
    for metric in metrics:
        row_values = []
        for dim in dim_list:
            key = f"dim_{dim}_cosine_{metric}"
            row_values.append(results[key])
        print(f"{metric:15}", end="  ")
        for val in row_values:
            print(f"{val:10.4f}", end=" ")
        print()
    print("-" * 85)
    print(f"sequential_score: {results['sequential_score']:.4f}\n")
    return results

def save_metrics_to_file(before: Dict, after: Dict, dim_list: List[int], path="metrics_comparison.txt"):
    metrics = [
        "ndcg@10", "mrr@10", "map@100",
        "accuracy@1", "accuracy@3", "accuracy@5", "accuracy@10",
        "precision@1", "precision@3", "precision@5", "precision@10",
        "recall@1", "recall@3", "recall@5", "recall@10",
    ]
    
    # Calculate maximum width needed for metrics
    max_metric_width = max(len(metric) for metric in metrics)
    dim_width = 8  # Width for each dimension's values
    
    with open(path, "w", encoding="utf-8") as f:
        # Write title
        title = "Model Performance Metrics Comparison"
        f.write(f"\n{title}\n")
        f.write("=" * len(title) + "\n\n")
        
        # Create dimension headers
        dims_section = "".join(f"{dim:>{dim_width}d}" for dim in dim_list)
        header = f"{'Metric':<{max_metric_width}} │ {'Before':>{len(dims_section)}} │ {'After':>{len(dims_section)}} │ {'Δ':>{len(dims_section)}}\n"
        subheader = f"{' ' * max_metric_width} │ {dims_section} │ {dims_section} │ {dims_section}\n"
        
        # Write headers
        f.write(header)
        f.write(subheader)
        f.write("─" * max_metric_width + "─┼─" + "─" * len(dims_section) + "─┼─" + "─" * len(dims_section) + "─┼─" + "─" * len(dims_section) + "\n")
        
        # Write metric rows
        for metric in metrics:
            before_vals = []
            after_vals = []
            diff_vals = []
            
            for dim in dim_list:
                key = f"dim_{dim}_cosine_{metric}"
                val_before = before[key]
                val_after = after[key]
                diff = val_after - val_before if val_before != 0 else 0
                
                before_vals.append(f"{val_before:{dim_width}.3f}")
                after_vals.append(f"{val_after:{dim_width}.3f}")
                diff_vals.append(f"{diff:{dim_width}.3f}")
            
            f.write(f"{metric:<{max_metric_width}} │ {''.join(before_vals)} │ {''.join(after_vals)} │ {''.join(diff_vals)}\n")
        
        # Write footer with sequential scores
        f.write("─" * max_metric_width + "─┴─" + "─" * len(dims_section) + "─┴─" + "─" * len(dims_section) + "─┴─" + "─" * len(dims_section) + "\n\n")
        
        # Add sequential scores
        sb = before["sequential_score"]
        sa = after["sequential_score"]
        ds = sa - sb
        f.write("Sequential Scores\n")
        f.write("----------------\n")
        f.write(f"Before: {sb:.3f}\n")
        f.write(f"After:  {sa:.3f}\n")
        f.write(f"Δ:      {ds:+.3f}\n")

def main(config):
    """Main training function."""
    if not hasattr(config, 'training') or not config.training:
        raise ValueError("Training configuration is required but not provided")

    # Get paths from config
    kb_path = config.chunker_config.output_path
    train_path = config.question_generation.output_path if config.question_generation else None

    # Verify files exist
    if not os.path.exists(kb_path):
        raise FileNotFoundError(f"Knowledgebase file not found: {kb_path}")
    if train_path and not os.path.exists(train_path):
        raise FileNotFoundError(f"Training data file not found: {train_path}")

    # Load knowledge base data
    with open(kb_path, "r", encoding="utf-8") as f:
        kb_data = json.load(f)

    # Load and prepare training dataset
    train_dataset_full = load_dataset("json", data_files=train_path, split="train")
    if "id" not in train_dataset_full.column_names:
        train_dataset_full = train_dataset_full.add_column("id", list(range(len(train_dataset_full))))
    if "chunk_id" in train_dataset_full.column_names:
        train_dataset_full = train_dataset_full.rename_column("chunk_id", "global_chunk_id")
    train_dataset_full = train_dataset_full.shuffle()
    dataset_split = train_dataset_full.train_test_split(test_size=0.1)
    train_dataset = dataset_split["train"]
    test_dataset = dataset_split["test"]
    logger.info(f"Train size: {len(train_dataset)} | Test size: {len(test_dataset)}")

    # Build evaluation structures
    corpus, queries, relevant_docs = build_evaluation_structures(
        kb_dataset=kb_data,
        test_dataset=test_dataset,
        kb_id_field="id",
        kb_text_field="text"
    )

    # Setup evaluators
    dim_list = config.training.matryoshka_dimensions
    evaluators = []
    for d in dim_list:
        evaluators.append(
            InformationRetrievalEvaluator(
                queries=queries,
                corpus=corpus,
                relevant_docs=relevant_docs,
                name=f"dim_{d}",
                score_functions={"cosine": cos_sim},
                truncate_dim=d
            )
        )
    evaluator = SequentialEvaluator(evaluators)

    # Initialize base model and run baseline evaluation
    device = "cuda" if torch.cuda.is_available() else "cpu"
    base_model = SentenceTransformer(config.training.model_id, device=device)
    baseline_results = run_baseline_eval(base_model, evaluator, dim_list)

    logger.info("Re-initializing for training.")
    model = SentenceTransformer(
        config.training.model_id,
        device=device,
        model_kwargs={"attn_implementation": "sdpa"},
        model_card_data=SentenceTransformerModelCardData(
            language="en",
            license="apache-2.0",
            model_name="Fine-tuned with [QuicKB](https://github.com/ALucek/QuicKB)",
        ),
    )

    # Setup loss functions
    base_loss = MultipleNegativesRankingLoss(model)
    train_loss = MatryoshkaLoss(
        model=model,
        loss=base_loss,
        matryoshka_dims=dim_list
    )

    # Setup training arguments
    args = SentenceTransformerTrainingArguments(
        output_dir=config.training.output_path,
        num_train_epochs=config.training.epochs,
        per_device_train_batch_size=config.training.batch_size,
        gradient_accumulation_steps=config.training.gradient_accumulation_steps,
        learning_rate=config.training.learning_rate,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        optim="adamw_torch_fused",
        tf32=True,
        bf16=True,
        batch_sampler=BatchSamplers.NO_DUPLICATES,
        eval_strategy="epoch",
        save_strategy="epoch",
        logging_steps=10,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model=config.training.metric_for_best_model,
        report_to="none",
    )

    # Prepare final training dataset and trainer
    final_train_dataset = train_dataset.select_columns(["anchor", "positive"])
    trainer = SentenceTransformerTrainer(
        model=model,
        args=args,
        train_dataset=final_train_dataset,
        loss=train_loss,
        evaluator=evaluator,
    )

    # Train model
    logger.info("Starting training...")
    trainer.train()
    trainer.save_model()
    
    # Evaluate fine-tuned model
    fine_tuned_model = SentenceTransformer(config.training.output_dir, device=device)
    final_results = run_final_eval(fine_tuned_model, evaluator, dim_list)

    # Save metrics
    save_metrics_to_file(
        baseline_results, 
        final_results, 
        dim_list, 
        path=f"{config.training.output_dir}/metrics_comparison.txt"
    )

    # Handle model upload if configured
    if config.training.push_to_hub:
        HF_TOKEN = os.getenv("HF_TOKEN", "")
        if HF_TOKEN:
            login(token=HF_TOKEN)
        else:
            logger.warning("No HF_TOKEN in env, attempting login anyway.")
            
        if not config.training.hub_model_id:
            logger.warning("No hub_model_id specified, skipping upload")
        else:
            logger.info(f"Pushing model to HF Hub: {config.training.hub_model_id}")
            trainer.model.push_to_hub(
                config.training.hub_model_id, 
                exist_ok=True, 
                private=config.training.hub_private
            )
            logger.info("Upload complete!")

    logger.info("Training pipeline finished.")

if __name__ == "__main__":
    main()
