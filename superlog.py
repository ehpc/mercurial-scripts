"""superlog displays a detailed log
"""
from mercurial import ui, hg, cmdutil, commands
from mercurial.i18n import _
from subprocess import check_output, call
import pprint

cmdtable = {}
command = cmdutil.command(cmdtable)

@command(
    'superlog',
    [],
    ''
)

def superlog(ui, repo, rev, **opts):
    """Displays a detailed log
    """
    cmd = '(hg paths && hg log --stat -v -r %s)' % rev
    clipCmd = '(%s > superlog.log) && (chcp 1251 && clip < superlog.log)' % cmd
    call(clipCmd, shell=True)
    ui.write(check_output(cmd, shell=True))
    call('del superlog.log', shell=True)

def superlogHook(ui, repo, **kwargs):
    """On commit hook
    """
    superlog(ui, repo, repo['tip'].rev())
