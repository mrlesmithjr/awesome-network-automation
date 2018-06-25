#!/usr/bin/env python

"""Sync forked repos.

This script ensures that the repo that this was forked from is added as a
git remote called upstream. Once the upstream remote is configured, this script
will then fetch any changes in the upstream remote, merge any changes, commit
the changes, and then finally push the changes to the forked repo.
"""

# Requirements:
# pip install gitpython

import datetime
import logging
import os
import sys

# Defines the log file name and location of where to log to
LOG_FILE = "sync-repo.log"

# Defines the upstream repo this repo was forked from
# Example: UPSTREAM="git@gitlab.com:mrlesmithjr/test-repo.git"
UPSTREAM = "https://github.com/itdependsnetworks/awesome-network-automation.git"

# Defines the upstream branch to sync with. Important for those that are not
# by default master.
UPSTREAM_BRANCH = "master"

def main():
    """Main function of execution."""
    # Defining different formats to use for logging output
    console_logging_format = "%(levelname)s: %(message)s"
    file_logging_format = "%(levelname)s: %(asctime)s: %(message)s"

    # Configuring logger
    logging.basicConfig(level=logging.INFO, format=console_logging_format)
    logger = logging.getLogger()

    # Creating file handler for output file
    handler = logging.FileHandler(LOG_FILE)

    # Configuring logging level for log file
    handler.setLevel(logging.INFO)

    # Configuring logging format for log file
    formatter = logging.Formatter(file_logging_format)
    handler.setFormatter(formatter)

    # Adding handlers to the logger
    logger.addHandler(handler)

    logger.info('Started')

    try:
        from git import Repo
    except ImportError as error:
        # Output expected ImportErrors.
        logger.error(error.__class__.__name__ + ": " + error.message)
        logger.error("Please install GitPython module...")
        sys.exit(0)
    except Exception as exception:
        # Output unexpected Exceptions.
        logger.exception(exception, False)
        logger.exception(error.__class__.__name__ + ": " + exception.message)
        sys.exit(0)

    # Capturing current working directory
    repo_path = os.getcwd()

    # Defining repo based on current working directory
    repo = Repo(repo_path, search_parent_directories=True)

    # Check to make sure that we are not working in a bare repo
    assert not repo.bare

    # Capturing current active branch
    current_branch = repo.active_branch

    # Setting up repository remotes
    repo_remotes(logger, repo)

    # Check for any upstream changes
    upstream_changes = check_upstream_changes(repo)

    if upstream_changes:

        # Check for any changes and stash them before proceeding
        stashed_changes = stash_changes(logger, repo)

        # Syncing upstream with local repository
        sync_upstream(logger, repo, current_branch)

        # Updating and syncing any submodules being used
        update_submodules(logger, repo, repo_path, Repo)

        # Committing and pushing any changes from upstream to forked repo.
        commit_changes(logger, repo, current_branch)

        # Popping any stashed changes
        stash_pop_changes(logger, repo, stashed_changes)

    else:
        logger.info("No upstream changes found.")

    logger.info('Finished')


def check_upstream_changes(repo):
    """Check for any upstream changes."""
    fetch_upstream = repo.remotes.upstream.fetch()[0]
    if fetch_upstream.flags == 4:
        upstream_changes = False
    else:
        upstream_changes = True
    return upstream_changes


def commit_changes(logger, repo, current_branch):
    """Commit and push changes to fork."""
    try:
        logger.info("Committing any new changes...")
        repo.git.commit('-m', '"upstream synced"')
        logger.info("Any new changes have been committed.")
    except:
        logger.info("No changes have been found to commit.")
    logger.info("Pushing any new changes to forked repo...")
    repo.git.push()
    logger.info("All new changes have been pushed to forked repo.")
    tagging(logger, repo)
    logger.info("Pushing any tags.")
    repo.git.push('--tags')
    if current_branch.name != UPSTREAM_BRANCH:
        logger.info("Checking out original branch: " + current_branch.name)
        repo.git.checkout(current_branch.name)
        logger.info("Rebasing with local %s to include any changes." % UPSTREAM_BRANCH)
        repo.git.rebase(UPSTREAM_BRANCH)


def get_status(logger, repo):
    """Get status of local repo and check for changes."""
    # Capturing any untracked files in local repository. Future use cases..
    untracked_files = repo.untracked_files
    if untracked_files != []:
        logger.info("The following untracked files were found and "
              "should be committed: ")
        for item in untracked_files:
            logger.info(item)
    changes = []
    for item in repo.index.diff(None):
        changes.append(item.a_path)
    return changes


def repo_remotes(logger, repo):
    """Check for existing upstream repository remote."""
    remotes = []
    for remote in repo.remotes:
        remotes.append(remote.name)
    if "upstream" not in remotes:
        logger.info("upstream remote not found. Adding...")
        repo.create_remote("upstream", UPSTREAM)
        logger.info("upstream remote added successfully.")
    else:
        if repo.remotes.upstream.url != UPSTREAM:
            logger.info("upstream remote found but not correct. Changing...")
            repo.delete_remote("upstream")
            repo.create_remote("upstream", UPSTREAM)
            logger.info("upstream remote successfully changed.")


def stash_changes(logger, repo):
    """Stash local changes.

    Stash any local changes to ensure no failures occur when checking out
    UPSTREAM_BRANCH.
    """
    logger.info("Checking status of repo changes..")
    changes = get_status(logger, repo)
    if changes != []:
        logger.info("Stashing the following uncommitted entries:")
        for item in changes:
            logger.info(item)
        repo.git.stash()
        stashed_changes = True
    else:
        logger.info("No uncommitted entries found.")
        stashed_changes = False
    return stashed_changes


def stash_pop_changes(logger, repo, stashed_changes):
    """Pop all stashed changes to ensure any existing changes are not lost."""
    if stashed_changes is True:
        logger.info("Popping any stashed entries.")
        repo.git.stash('pop')


def sync_upstream(logger, repo, current_branch):
    """Sync upstream parent repo.

    Sync upstream repo, merge changes, commit changes, and push changes to
    fork.
    """
    if current_branch.name != UPSTREAM_BRANCH:
        logger.info("Checking out %s branch..." % UPSTREAM_BRANCH)
        repo.git.checkout(UPSTREAM_BRANCH)
        logger.info("%s branch checked out." % UPSTREAM_BRANCH)
    logger.info("Merging any changes from upstream/%s..." % UPSTREAM_BRANCH)
    repo.git.merge('upstream/%s' % UPSTREAM_BRANCH)
    logger.info("Any changes from upstream/%s merged." % UPSTREAM_BRANCH)


def tagging(logger, repo):
    """Create automatic tagging based on timestamp when commits are made."""
    tags = repo.tags
    if tags != []:
        logger.info("The following tags were found: ")
        for tag in tags:
            logger.info(tag)
    tag = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    logger.info("Creating new tag: " + tag)
    repo.create_tag(tag, message='Automatic tag created on: %s' % tag)


def update_submodules(logger, repo, repo_path, Repo):
    """Update any git submodules used."""
    logger.info("Gathering all submodules...")
    # Collect any submodules in use
    sms = repo.submodules
    # Ensure that there are actually submodules in use
    if len(sms) > 0:
        # Iterate over each submodule found
        for sm in sms:
            # Define submodule actual path
            sm_path = repo_path + "/" + sm.path
            # Define submodule repo
            sm_repo = Repo(sm_path)
            # Check for any changed files
            sm_changed_files = sm_repo.index.diff(None)
            if sm_changed_files != []:
                logger.info("Stashing changed files found in submodule: %s" % sm.name)
                # Stash any changed files found in submodule
                sm_repo.git.stash()
                sm_stashed_files = True
            else:
                sm_stashed_files = False
            # Collect any untracked files in submodule
            sm_untracked_files = sm_repo.untracked_files
            if sm_untracked_files != []:
                logger.info("The following untracked files found in submodule: %s"
                % sm_untracked_files)
            # Update the submodule
            logger.info("Updating submodule: %s" % sm.name)
            sm_repo.submodule_update()
            if sm_stashed_files:
                logger.info("Popping stashed files found in submodule: %s" % sm.name)
                # Pop any stashed files found in submodule
                sm_repo.git.stash('pop')
    else:
        logger.info("No submodules found.")


if __name__ == "__main__":
    main()
