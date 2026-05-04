
# Git Bare Repositories with Worktrees

This approach to git creates an outer management dir that is not the checked out repo, a "bare" dir that is for git internal data,
and then multiple worktree directories that can have different branches checked out simultaneously.

Some reasons to work this way:
* W can leave work-in-progress in one worktree without committing or branching, and attend to a different branch.
* W can have agents work in different worktrees simultaneously.
* W can put sensitive material, e.g. customer data, secrets, in the outer dir where it cannot possibly get checked in by accident.

Many guides suggest using `.bare` for the bare dir, but I am using `_bare` so that it is visible, to make the developer aware of the setup at a glance.

```
git clone --bare git@github.com:org/repo.git _bare # Clone git data into _bare without setting it up as a usable repo root.
echo "gitdir: ./_bare" > .git # This allows us to issue git commands from the outer management directory

# Configure the remote manually and fetch.
git config remote.origin.fetch '+refs/heads/*:refs/remotes/origin/*'
git fetch origin

# Create a 'main' worktree.
 git worktree add main main
 cd main
