# AI Engineering Skill

## Model Selection Framework

### By Task Type
- **Text generation/chat:** GPT-4o, Claude 3.5 Sonnet, Llama 3.1
- **Code generation:** GPT-4o, Claude 3.5 Sonnet, CodeLlama
- **Embeddings:** text-embedding-3-small/large, BGE, E5
- **Image recognition:** GPT-4o Vision, Claude Vision, CLIP
- **Classification:** Fine-tuned smaller models or few-shot with GPT-4o-mini

### Cost vs Quality Tiers
- **Premium:** GPT-4o, Claude Opus — complex reasoning, important outputs
- **Standard:** GPT-4o-mini, Claude Sonnet — most production tasks
- **Economy:** Llama 3.1, Mistral — high volume, lower complexity
- **Local:** Ollama + quantized models — privacy-first, offline

## Prompt Engineering Best Practices
1. Be specific about output format
2. Provide examples (few-shot)
3. Use system messages for role/constraints
4. Chain-of-thought for complex reasoning
5. Set temperature low (0.1-0.3) for consistency
6. Test with edge cases before production

## ML Pipeline Design
1. Define success metric FIRST
2. Start with the simplest approach that could work
3. Use existing pre-trained models before training custom
4. Build evaluation pipeline before training pipeline
5. Monitor for drift in production

## Responsible AI Checklist
- Bias assessment on training/test data
- Fairness across demographic groups
- Explainability for high-stakes decisions
- Human oversight for critical actions
- Privacy: no PII in training data without consent
