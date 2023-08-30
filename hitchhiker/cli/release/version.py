import os
import re
import git
import github
import click
import hitchhiker.release.version.commit as commit
import hitchhiker.cli.release.config as config
import hitchhiker.release.enums as enums
import hitchhiker.release.changelog as changelog


@click.command(short_help="Figure out new version and apply it")
@click.option("--show", is_flag=True, default=False, help="print versions and exit")
@click.option("--prerelease", is_flag=True, default=False, help="do prereleases")
@click.option("--push", is_flag=True, default=False, help="push to origin")
@click.option("--ghrelease", is_flag=True, default=False, help="create github release")
@click.pass_context
def version(ctx: click.Context, show, prerelease, push, ghrelease):
    """Figure out new version and apply it"""
    if show:
        print(f"main version: {ctx.obj['RELEASE_CONF'].version}")
        for project in ctx.obj["RELEASE_CONF"].projects:
            print(f"project: {project.name} version: {project.version}")
        return

    print(f"main version: {ctx.obj['RELEASE_CONF'].version}")
    mainbump = enums.VersionBump.NONE
    changedfiles = []
    change_commits = {}
    for project in ctx.obj["RELEASE_CONF"].projects:
        print(f"project: {project.name} version: {project.version}")
        bump, commits = commit.find_next_version(ctx.obj["RELEASE_CONF"], project, prerelease)
        mainbump = bump if bump > mainbump else mainbump
        if bump != enums.VersionBump.NONE:
            if not prerelease:
                project.version.remove_prerelease()
            project.version.bump(bump, prerelease)

            if project.name not in change_commits:
                change_commits[project.name] = [project.version, []]
            change_commits[project.name][1] += [commitmsg for commitmsg, _ in commits]

            changedfiles += config.set_version(ctx.obj["RELEASE_CONF"], project)
            print(f"-- new -- project: {project.name} version: {project.version}")

    if mainbump != enums.VersionBump.NONE:
        if not prerelease:
            ctx.obj["RELEASE_CONF"].version.remove_prerelease()
        ctx.obj["RELEASE_CONF"].version.bump(mainbump, prerelease)
        changedfiles += config.set_version(ctx.obj["RELEASE_CONF"], ctx.obj["RELEASE_CONF"])
        print(f"main version bump: {ctx.obj['RELEASE_CONF'].version}")

    if len(changedfiles) > 0:
         # regex from: https://stackoverflow.com/a/25102190
        try:
            _match = re.match(
            r"^(?:(?:git@|https:\/\/)(?:[\w\.@]+)(?:\/|:))([\w,\-,\_]+)\/([\w,\-,\_]+)(?:.git){0,1}(?:(?:\/){0,1})$",
            git.cmd.Git(ctx.obj["RELEASE_CONF"].repo.working_tree_dir).execute(
                ["git", "config", "--get", "remote.origin.url"]
            ),
            )
            repo_owner = _match.group(1) if _match is not None else None
            repo_name = _match.group(2) if _match is not None else None
        except:
            repo_owner = None
            repo_name = None

        changelog_path = os.path.join(ctx.obj['RELEASE_CONF'].repo.working_tree_dir, "CHANGELOG.md")
        changelog_newtext = changelog.gen_changelog(change_commits=change_commits, new_version=str(ctx.obj["RELEASE_CONF"].version), repo_owner= repo_owner, repo_name=repo_name)
        if not os.path.isfile(changelog_path):
            with open(changelog_path, "w") as f:
                f.write("# CHANGELOG\n" + changelog_newtext)
        else:
            with open(changelog_path, "a") as f:
                f.write(changelog_newtext)
        changedfiles.append("CHANGELOG.md")

        ctx.obj["RELEASE_CONF"].repo.git.add(changedfiles)
        ctx.obj["RELEASE_CONF"].repo.git.commit(m=f"{str(ctx.obj['RELEASE_CONF'].version)}\n\nAutogenerated by hitchhiker")
        newtag = f"v{str(ctx.obj['RELEASE_CONF'].version)}"
        if newtag not in [tag.name for tag in ctx.obj["RELEASE_CONF"].repo.tags]:
            ctx.obj["RELEASE_CONF"].repo.git.tag("-a", newtag, m=newtag)
        else:
            print(f'tag "{newtag}" already exists')
        if push:
            try:
                ctx.obj["RELEASE_CONF"].repo.remote(name="origin").push().raise_if_error()
            except: # TODO: figure out which exceptions could be thrown here
                raise click.ClickException(message="Failed to push")
        if ghrelease:
            tokenstr = os.getenv("GITHUB_TOKEN")
            if tokenstr is None:
                raise click.ClickException(message="Failed to get \"GITHUB_TOKEN\" environment variable")
            try:
                auth = github.Auth.Token(tokenstr)
                gh = github.Github(auth=auth)
            except: # TODO: figure out which exceptions could be thrown here
                raise click.ClickException(message="Failed to authenticate at GitHub with token")

            if repo_owner is None or repo_name is None:
                raise click.ClickException(message="could not parse remote URL to get owner & repository name")

            try:
                repo = gh.get_repo(f"{repo_owner}/{repo_name}")
            except: # TODO: figure out which exceptions could be thrown here
                raise click.ClickException(message="Failed to get repository from github")
            
            try:
                repo.create_git_release(
                    tag=newtag,
                    name=newtag,
                    message=changelog_newtext,
                    prerelease=prerelease,
                    target_commitish=ctx.obj["RELEASE_CONF"].repo.commit(ctx.obj["RELEASE_CONF"].repo.active_branch).hexsha,
                )
            except:
                raise click.ClickException(message="Failed to create release on GitHub")
