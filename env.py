import click
import pathlib
import subprocess
import sys


FRAMEWORKS_PATH     = pathlib.Path(__file__).parent.parent / 'frameworks'
SITE_PACKAGES_GLOB  = 'lib/python*/site-packages'
PYTHON_BIN          = f'{sys.prefix}/bin/python'


class Configuration:

    def __init__(self, verbose):
        self._verbose = verbose

    @property
    def verbose(self):
        return self._verbose


pass_configuration = click.make_pass_decorator(Configuration)


def _get_frameworks_paths():
    return [f for f in FRAMEWORKS_PATH.glob('*') if f.is_dir()]


@click.group()
@click.option(
    '-v', '--verbose',
    is_flag         = True,
    default         = False,
    help            = 'verboseness',
    show_default    = True,
)
@click.pass_context
def cli(ctx, verbose):
    ctx.obj = Configuration(verbose)


@cli.command()
@pass_configuration
def list(configuration):
    for framework in _get_frameworks_paths():
        print(framework)


@cli.command()
@click.option(
    '--site-dir',
    type    = click.Path(exists=True, file_okay=False, dir_okay=True),
    help    = 'site-packages directory to install (otherwise finds it automatically)',
)
@click.option(
    '--dependencies',
    is_flag = True,
    help    = 'whether or not install framework dependencies req files',
)
@click.option(
    '--project',
    is_flag = True,
    help    = 'whether or not add directory as pth',
)
@pass_configuration
def install(configuration, site_dir, dependencies, project):
    prefix  = pathlib.Path(sys.prefix)
    site    = [pathlib.Path(site_dir)] if site_dir else [path for path in prefix.glob(SITE_PACKAGES_GLOB)]

    if not site:
        raise RuntimeError(f'could not find site package dir: {prefix}/{SITE_PACKAGES_GLOB}')

    site = site[0]
    print(f'installing in site packages directory: {site}')

    for framework in _get_frameworks_paths():
        framework_pth   = site / f'{framework.name}.pth'
        framework_path  = framework.resolve()
        print(f'creating pth: {framework_pth} with content: {framework_path}')
        framework_pth.write_text(f'{framework_path}')

    if dependencies:
        for framework in _get_frameworks_paths():
            reqs = [req for req in framework.glob('requirements*') if req.is_file()]
            minus_r = []
            for req in reqs:
                minus_r.extend(['-r', f'{req}'])
            print(f'installing requirements for {framework}: {", ".join(str(req) for req in reqs)}')
            ret = subprocess.run(
                args            = [
                    PYTHON_BIN,
                    '-m',
                    'pip',
                    'install',
                ] + minus_r,
                capture_output  = True,
            )
            if ret.returncode:
                print('failed to install requirements')
            if ret.returncode or configuration.verbose:
                print('STDERR')
                print(ret.stderr.decode())
                print('STDOUT')
                print(ret.stdout.decode())

    if project:
        project_dir     = pathlib.Path(__file__).parent
        project_pth     = site / f'{project_dir.name}.pth'
        project_path    = project_dir.resolve()
        print(f'creating project pth: {project_pth} with content: {project_path}')
        project_pth.write_text(f'{project_path}')

    print('done')


if __name__ == '__main__':
    cli()
