# GPT Prompt Templates

This directory contains prompt templates for analyzing WalletDoctor trade data using ChatGPT or other LLMs. The templates are designed to provide structured analysis with consistent formatting.

## Template Categories

### 1. Basic Analysis (`basic_analysis.md`)
Simple prompts for quick insights without complex reasoning chains.

### 2. Chain-of-Thought Analysis (`chain_of_thought_analysis.md`)
Advanced prompts that guide the model through step-by-step reasoning for deeper insights.

### 3. Token Optimization (`token_optimized.md`)
Efficient prompts designed to minimize token usage while maintaining quality.

## Usage Guidelines

1. **Replace Placeholders**: All templates use `{{WALLET_DATA}}` as a placeholder for the actual trade data JSON.

2. **Token Costs**: Each template includes estimated token costs based on GPT-4 pricing.

3. **Output Disclaimers**: Templates include "Example Output" sections clearly marked to prevent training contamination.

4. **Customization**: Feel free to modify templates based on your specific analysis needs.

## Best Practices

- Start with basic analysis for quick insights
- Use chain-of-thought for complex pattern recognition
- Monitor token usage for cost optimization
- Always validate insights against raw data

## Integration Example

```python
# Using with the TypeScript client
const client = new WalletDoctorClient({ apiKey: 'wd_your_key' });
const trades = await client.exportTrades(wallet);

// Insert trade data into prompt template
const prompt = template.replace('{{WALLET_DATA}}', JSON.stringify(trades));
``` 