#!/bin/bash
# Create PR for GPT Integration CI Workflow

# Ensure we're on the latest main
git checkout main
git pull origin main

# Create feature branch
BRANCH_NAME="gpt-006-ci-workflow"
git checkout -b $BRANCH_NAME

# Add the workflow file
git add .github/workflows/gpt-integration.yml
git add schemas/VERSIONING.md

# Commit with descriptive message
git commit -m "feat(ci): Add GPT integration test workflow with performance monitoring

- Add daily scheduled tests for GPT export endpoints
- Implement performance warning bands (cold >6s, warm >0.3s)
- Add schema validation checks
- Configure single concurrent job to prevent DOS
- Include Slack notifications for failures
- Test against small wallet only until CCH-001 lands

Addresses GPT-006 requirements for CI/CD testing"

# Push the branch
git push -u origin $BRANCH_NAME

# Create PR using GitHub CLI (if installed)
if command -v gh &> /dev/null; then
    echo "Creating PR with GitHub CLI..."
    gh pr create \
        --title "feat(ci): GPT Integration Test Workflow" \
        --body "## Summary
Implements GPT-006 CI requirements with performance monitoring and warning bands.

## Changes
- ✅ Daily scheduled tests at 9 AM UTC
- ✅ Performance warning bands (don't block PRs)
  - Cold: Fail >8s, Warn >6s
  - Warm: Fail >0.5s, Warn >0.3s
- ✅ Schema validation using GPT-002 files
- ✅ Single concurrent job (prevents DOS)
- ✅ Slack notifications for scheduled failures
- ✅ Parameterized for easy forking

## Testing
- Small wallet only until CCH-001 (Redis) lands
- Warm/cold performance checks with annotations
- Auth error handling validation

## Next Steps
After merge:
- [ ] Add badge to README
- [ ] Monitor first scheduled run
- [ ] Adjust thresholds based on real data

Closes GPT-006" \
        --reviewer "@your-github-username" \
        --label "gpt-integration,ci/cd"
else
    echo "GitHub CLI not installed. Please create PR manually at:"
    echo "https://github.com/$(git remote get-url origin | sed 's/.*github.com[:/]\(.*\)\.git/\1/')/compare/$BRANCH_NAME?expand=1"
    echo ""
    echo "PR Title: feat(ci): GPT Integration Test Workflow"
    echo ""
    echo "Use this description:"
    echo "---"
    cat << 'EOF'
## Summary
Implements GPT-006 CI requirements with performance monitoring and warning bands.

## Changes
- ✅ Daily scheduled tests at 9 AM UTC
- ✅ Performance warning bands (don't block PRs)
  - Cold: Fail >8s, Warn >6s
  - Warm: Fail >0.5s, Warn >0.3s
- ✅ Schema validation using GPT-002 files
- ✅ Single concurrent job (prevents DOS)
- ✅ Slack notifications for scheduled failures
- ✅ Parameterized for easy forking

## Testing
- Small wallet only until CCH-001 (Redis) lands
- Warm/cold performance checks with annotations
- Auth error handling validation

## Next Steps
After merge:
- [ ] Add badge to README
- [ ] Monitor first scheduled run
- [ ] Adjust thresholds based on real data

Closes GPT-006
EOF
fi

echo ""
echo "✅ Branch '$BRANCH_NAME' created and pushed!"
echo "📝 Don't forget to tag the reviewer!" 