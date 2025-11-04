# Architecture Monitoring Configuration

## Thresholds and Quality Gates

### File Size Limits
- **Target**: < 500 lines per file
- **Warning**: 500-1000 lines  
- **Critical**: > 1000 lines (requires immediate refactoring)

### Complexity Limits
- **Target**: < 30 complexity score
- **Warning**: 30-50 complexity score
- **Critical**: > 50 complexity score

### Architecture Score
- **Excellent**: 90-100 points
- **Good**: 75-89 points  
- **Needs Attention**: 60-74 points
- **Critical**: < 60 points

## Usage

### Manual Monitoring
```bash
# Run architecture analysis
python scripts/monitor_architecture.py

# View metrics history
cat architecture_metrics.json
```

### Automated CI/CD Integration
```yaml
# GitHub Actions example
- name: Architecture Quality Check
  run: python scripts/monitor_architecture.py
```

### Pre-commit Hook Setup
```bash
# Install pre-commit hook
cp scripts/pre_commit_arch_check.py .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

## Metrics Tracked

1. **File Statistics**
   - Total Python files
   - Total lines of code
   - Average file size
   - Files over size thresholds

2. **Code Quality**
   - Complexity scores per file
   - Largest file identification
   - Duplicate file detection

3. **Architecture Health**
   - Overall architecture score
   - Trend analysis over time
   - Actionable recommendations

## Quality Gates for CI/CD

- Largest file must be < 1500 lines
- Maximum 5 files over 1000 lines
- Architecture score must be ≥ 60
- Maximum 2 duplicate files allowed

## Integration Examples

### GitHub Actions
```yaml
name: Architecture Check
on: [push, pull_request]
jobs:
  architecture:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Setup Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Check Architecture
        run: python scripts/monitor_architecture.py
```

### Local Development
```bash
# Add to Makefile
arch-check:
    python scripts/monitor_architecture.py

# Add to package.json scripts
"scripts": {
  "arch-check": "python scripts/monitor_architecture.py"
}
```