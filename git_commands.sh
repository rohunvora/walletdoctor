#!/bin/bash
# Git commands to push the latest changes

echo "🚀 Pushing WalletDoctor Deep Insight System updates..."

# Add core system files
git add src/
git add requirements.txt
git add README.md

# Add test files
git add test_insight_engine.py
git add test_with_csv_data.py
git add test_real_wallet.py
git add test_deep_analysis.py
git add test_validated_deep_insights.py

# Add demo files
git add deep_analysis_example.py
git add show_deep_vs_shallow.py
git add example_full_narrative.py
git add final_deep_insights_demo.py

# Add documentation
git add SCRATCHPAD.md
git add CHANGES_SUMMARY.md

# Commit with descriptive message
git commit -m "feat: Add deep psychological insight system with statistical validation

- Add pattern detection for behavioral analysis (loss aversion, revenge trading, etc)
- Implement statistical validation to prevent false conclusions  
- Create psychological mapping to reveal subconscious drivers
- Add confidence scores and effect size calculations
- Integrate harsh truth delivery system
- Update README with new deep analysis features
- Add comprehensive test suite and demos

Key improvements:
- Detects 5 behavioral patterns with multi-metric analysis
- Validates with p-values, Cohen's d, and temporal consistency
- Maps patterns to psychological roots and subconscious narratives
- Provides specific, measurable fixes (not vague advice)
- Shows confidence levels to prevent overconfidence in insights

This transforms WalletDoctor from basic metrics reporting to deep psychological
analysis that actually changes trader behavior."

# Show what was committed
echo ""
echo "📝 Files committed:"
git diff --name-only HEAD~1

# Show status
echo ""
git status

echo ""
echo "✅ Changes staged and committed!"
echo ""
echo "To push to remote repository, run:"
echo "  git push origin main"
echo ""
echo "Or if you're on a feature branch:"
echo "  git push origin your-branch-name"
echo ""
echo "To see the commit details:"
echo "  git show --stat" 