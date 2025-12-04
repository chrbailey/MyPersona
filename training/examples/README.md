# MyPersona Training Examples

## Total: 390 Examples

Training data for fine-tuning LLMs to understand what users REALLY mean based on context.

### By Scenario (270 examples)

| File | Count | Description |
|------|-------|-------------|
| `romantic_context.jsonl` | 30 | Social/dating situations, late night, attraction contexts |
| `work_stress.jsonl` | 30 | Professional settings, deadlines, meetings, work-life balance |
| `parental_context.jsonl` | 30 | Parenting situations, child safety, family dynamics |
| `health_safety.jsonl` | 30 | Health concerns, elderly care, veteran-specific needs |
| `quiet_reflective.jsonl` | 30 | Alone time, contemplation, when NOT to interrupt |
| `social_status.jsonl` | 30 | Networking, interviews, impression management |
| `comfort_elderly.jsonl` | 30 | Senior living, memory support, comfort seeking |
| `play_adventure.jsonl` | 30 | Children, young adults, fun-seeking, recreation |

### By Age (120 examples)

| File | Count | Life Stage Focus |
|------|-------|-----------------|
| `age_11.jsonl` | 20 | Play, competence, fitting in, school concerns |
| `age_21.jsonl` | 20 | Status, relationships, career start, independence |
| `age_31.jsonl` | 20 | Mate retention, early parenting, career building |
| `age_41.jsonl` | 20 | Legacy, mentoring, stability, midlife reflection |
| `age_61.jsonl` | 20 | Comfort, health, retirement, grandparenting |
| `age_81.jsonl` | 20 | Peace, connection, acceptance, memory support |

## Veteran-Specific Content

Many examples include veteran-specific contexts:
- TBI and cognitive processing challenges
- PTSD and hypervigilance scenarios
- Physical disabilities from service
- VA healthcare navigation
- Tinnitus and hearing issues
- Depression and anxiety management
- Social reintegration challenges

## Format

All files use JSONL format compatible with:
- Anthropic/Bedrock fine-tuning
- OpenAI fine-tuning
- HuggingFace Transformers
- Open source model training

```jsonl
{"system": "...", "messages": [{"role": "user", "content": "[CONTEXT]..."}, {"role": "assistant", "content": "..."}]}
```

## Usage

These examples teach models to:
1. Parse context signals before responding
2. Infer real intent from age + situation + query
3. Respond to meaning, not literal words
4. Know when to be brief vs detailed
5. Know when NOT to respond (quiet mode)

## License

Developed by ERP Access Inc., a Service-Disabled Veteran-Owned Small Business (SDVOSB).

Designed to help disabled veterans interact with AI systems more effectively.

Protected under Americans with Disabilities Act (ADA) accessibility provisions.
