import os
import re
import git
import github
import click
import hitchhiker.release.version.commit as commit
import hitchhiker.cli.release.config as config
import hitchhiker.release.enums as enums


@click.command(short_help="Figure out new version and apply it")
@click.option("--show", is_flag=True, default=False, help="print versions and exit")
@click.option("--prerelease", is_flag=True, default=False, help="do prereleases")
@click.option("--push", is_flag=True, default=False, help="push to origin")
@click.option("--ghrelease", is_flag=True, default=False, help="create github release")
@click.pass_context
def version(ctx: click.Context, show, prerelease, push, ghrelease):
    """Figure out new version and apply it"""
    if show:
        print(f"main version: {ctx.obj.version}")
        for project in ctx.obj.projects:
            print(f"project: {project.name} version: {project.version}")
        return

    print(f"main version: {ctx.obj.version}")
    mainbump = enums.VersionBump.NONE
    changedfiles = []
    for project in ctx.obj.projects:
        print(f"project: {project.name} version: {project.version}")
        bump, _ = commit.find_next_version(ctx.obj, project, prerelease)
        mainbump = bump if bump > mainbump else mainbump
        if bump != enums.VersionBump.NONE:
            if prerelease:
                project.version.bump_prerelease()
            else:
                project.version.remove_prerelease_and_buildmeta()
            project.version.bump(bump)
            changedfiles += config.set_version(ctx.obj, project)
            print(f"-- new -- project: {project.name} version: {project.version}")

    if mainbump != enums.VersionBump.NONE:
        if prerelease:
            ctx.obj.version.bump_prerelease()
        else:
            ctx.obj.version.remove_prerelease_and_buildmeta()
        ctx.obj.version.bump(mainbump)
        changedfiles += config.set_version(ctx.obj, ctx.obj)
        print(f"main version bump: {ctx.obj.version}")

    if len(changedfiles) > 0:
        ctx.obj.repo.git.add(changedfiles)
        ctx.obj.repo.git.commit(m=f"{str(ctx.obj.version)}\n\nAutogenerated by hitchhiker")
        newtag = f"v{str(ctx.obj.version)}"
        if newtag not in [tag.name for tag in ctx.obj.repo.tags]:
            ctx.obj.repo.git.tag("-a", newtag, m=newtag)
        else:
            print(f'tag "{newtag}" already exists')
        if push:
            ctx.obj.repo.remote(name="origin").push()
        if ghrelease:
            auth = github.Auth.Token(os.getenv("GITHUB_TOKEN"))
            gh = github.Github(auth=auth)
            # regex from: https://stackoverflow.com/a/25102190
            match = re.match(
                r"^(?:(?:git@|https:\/\/)(?:[\w\.@]+)(?:\/|:))([\w,\-,\_]+)\/([\w,\-,\_]+)(?:.git){0,1}(?:(?:\/){0,1})$",
                git.cmd.Git(ctx.obj.repo.working_tree_dir).execute(
                    ["git", "config", "--get", "remote.origin.url"]
                ),
            )
            assert match is not None
            # FIXME: error handling
            gh.get_repo(f"{match.group(1)}/{match.group(2)}").create_git_release(
                tag=newtag,
                name=newtag,
                message="",
                target_commitish=ctx.obj.repo.commit(ctx.obj.repo.active_branch).hexsha,
            )
