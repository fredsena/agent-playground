# Git Best Practices & Daily Commands

A guide for daily development workflows and strategies for handling the most common Git scenarios and conflicts.

## 🚀 Daily Workflow Essentials

### Starting Your Day
Always keep your local repository in sync with the remote team.
```bash
git fetch origin           # See what changed on the server
git pull origin main      # Pull and merge the latest changes
```

### Working on Features
Create individual branches for every task to keep `main` clean.
```bash
git checkout -b feature/my-new-task    # Create and switch to new branch
git add .                              # Stage all changes
git commit -m "feat: descriptive message"
git push -u origin feature/my-new-task # Push and set upstream
```

### Keeping Your Branch Modern
Periodically bring changes from `main` into your feature branch to prevent giant conflicts later.
```bash
git checkout feature/my-new-task
git merge main
```

---

## 🛡️ Handling Merge Conflicts

Conflicts happen when two people (or you and the remote) change the same line of code.

### 1. The Standard Way
When `git merge` or `git pull` fails with a conflict:
1. **Identify**: Open the files listed by Git.
2. **Resolve**: Look for the markers:
   ```text
   <<<<<<< HEAD (Your local changes)
   Your code here
   =======
   Their code here
   >>>>>>> branch-name (Remote changes)
   ```
3. **Stage & Commit**:
   ```bash
   git add <conflicted-file>
   git commit -m "chore: resolve merge conflicts"
   ```

### 2. The "Nuclear" Option (Force One Side)
If you know for a fact that one version is 100% correct, use these shortcuts:

**Keep YOUR local changes only:**
```bash
git checkout --ours path/to/file
git add path/to/file
git commit -m "Resolve conflict by keeping local changes"
```

**Keep THEIR remote changes only:**
```bash
git checkout --theirs path/to/file
git add path/to/file
git commit -m "Resolve conflict by keeping remote changes"
```

---

## 🆘 Troubleshooting Common Issues

### "I committed to the wrong branch!"
If you haven't pushed yet:
```bash
git reset --soft HEAD~1    # Undo the commit but keep changes staged
git checkout correct-branch
git commit -m "The same message"
```

### "I want to undo my last local commit entirely"
```bash
git reset --hard HEAD~1    # WARNING: This deletes your uncommitted changes
```

### "My remote tracking is messed up"
Use the command we used earlier to re-establish the link:
```bash
git push -u origin <your-branch-name>
```

---

## 💡 Pro Tips
- **Commit Often**: Smaller commits are much easier to merge and debug.
- **Write Good Messages**: Use prefixes like `feat:`, `fix:`, or `docs:` to make your history readable.
- **Stash**: If you need to switch branches but aren't ready to commit, use `git stash` to temporarily hide your changes, then `git stash pop` to bring them back later.
