#!/bin/bash
echo "🔧 Installing Git hooks..."
ln -sf ../../hooks/pre-commit .git/hooks/pre-commit
echo "✅ Git hooks installed successfully."
