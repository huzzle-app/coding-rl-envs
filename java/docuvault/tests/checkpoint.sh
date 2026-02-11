#!/bin/bash
# Checkpoint management for faster episode resets
# Usage:
#   ./checkpoint.sh save [name]     - Save current state
#   ./checkpoint.sh restore [name]  - Restore to saved state
#   ./checkpoint.sh list            - List available checkpoints
#   ./checkpoint.sh delete [name]   - Delete a checkpoint

set -e

CHECKPOINT_DIR="/logs/checkpoints"
DEFAULT_NAME="latest"

mkdir -p "$CHECKPOINT_DIR"

usage() {
    echo "Usage: $0 {save|restore|list|delete} [checkpoint_name]"
    echo ""
    echo "Commands:"
    echo "  save [name]     Save current git state (default: latest)"
    echo "  restore [name]  Restore to checkpoint (default: latest)"
    echo "  list            List all checkpoints"
    echo "  delete [name]   Delete a checkpoint"
    echo ""
    echo "Environment Variables:"
    echo "  CHECKPOINT_DIR  Directory for checkpoints (default: /logs/checkpoints)"
    exit 1
}

save_checkpoint() {
    local name="${1:-$DEFAULT_NAME}"
    local checkpoint_path="$CHECKPOINT_DIR/$name"

    echo "Saving checkpoint: $name"

    # Save git state
    mkdir -p "$checkpoint_path"

    # Store current branch/commit
    git rev-parse HEAD > "$checkpoint_path/commit"
    git branch --show-current > "$checkpoint_path/branch" 2>/dev/null || echo "HEAD" > "$checkpoint_path/branch"

    # Save uncommitted changes as a patch
    git diff HEAD > "$checkpoint_path/uncommitted.patch" 2>/dev/null || true
    git diff --staged > "$checkpoint_path/staged.patch" 2>/dev/null || true

    # Save list of untracked files
    git ls-files --others --exclude-standard > "$checkpoint_path/untracked.txt"

    # Copy untracked files
    mkdir -p "$checkpoint_path/untracked"
    while IFS= read -r file; do
        if [ -n "$file" ] && [ -f "$file" ]; then
            mkdir -p "$checkpoint_path/untracked/$(dirname "$file")"
            cp "$file" "$checkpoint_path/untracked/$file"
        fi
    done < "$checkpoint_path/untracked.txt"

    # Save metadata
    echo "$(date -Iseconds)" > "$checkpoint_path/timestamp"
    git log -1 --oneline > "$checkpoint_path/description"

    echo "Checkpoint saved: $checkpoint_path"
    echo "  Commit: $(cat "$checkpoint_path/commit" | head -c 8)"
    echo "  Time: $(cat "$checkpoint_path/timestamp")"
}

restore_checkpoint() {
    local name="${1:-$DEFAULT_NAME}"
    local checkpoint_path="$CHECKPOINT_DIR/$name"

    if [ ! -d "$checkpoint_path" ]; then
        echo "Error: Checkpoint '$name' not found"
        echo "Available checkpoints:"
        list_checkpoints
        exit 1
    fi

    echo "Restoring checkpoint: $name"

    # Reset to saved commit
    local commit=$(cat "$checkpoint_path/commit")
    git reset --hard "$commit"

    # Apply staged changes
    if [ -s "$checkpoint_path/staged.patch" ]; then
        git apply "$checkpoint_path/staged.patch" 2>/dev/null || true
        git add -A
    fi

    # Apply uncommitted changes
    if [ -s "$checkpoint_path/uncommitted.patch" ]; then
        git apply "$checkpoint_path/uncommitted.patch" 2>/dev/null || true
    fi

    # Restore untracked files
    if [ -d "$checkpoint_path/untracked" ]; then
        cp -r "$checkpoint_path/untracked/." . 2>/dev/null || true
    fi

    echo "Checkpoint restored: $name"
    echo "  Commit: $(echo $commit | head -c 8)"
}

list_checkpoints() {
    echo "Available checkpoints:"
    for dir in "$CHECKPOINT_DIR"/*/; do
        if [ -d "$dir" ]; then
            local name=$(basename "$dir")
            local timestamp=""
            local desc=""
            [ -f "$dir/timestamp" ] && timestamp=$(cat "$dir/timestamp")
            [ -f "$dir/description" ] && desc=$(cat "$dir/description")
            printf "  %-15s %s  %s\n" "$name" "$timestamp" "$desc"
        fi
    done
}

delete_checkpoint() {
    local name="${1:-}"
    if [ -z "$name" ]; then
        echo "Error: Checkpoint name required"
        exit 1
    fi

    local checkpoint_path="$CHECKPOINT_DIR/$name"
    if [ ! -d "$checkpoint_path" ]; then
        echo "Error: Checkpoint '$name' not found"
        exit 1
    fi

    rm -rf "$checkpoint_path"
    echo "Deleted checkpoint: $name"
}

# Main
case "${1:-}" in
    save)
        save_checkpoint "${2:-}"
        ;;
    restore)
        restore_checkpoint "${2:-}"
        ;;
    list)
        list_checkpoints
        ;;
    delete)
        delete_checkpoint "${2:-}"
        ;;
    *)
        usage
        ;;
esac
