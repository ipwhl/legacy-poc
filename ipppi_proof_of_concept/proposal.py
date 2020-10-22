# Package update proposal handling
# Copyright (C) 2020  Nguyễn Gia Phong
#
# This file is part of IPPPI.
#
# IPPPI is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# IPPPI is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with IPPPI.  If not, see <https://www.gnu.org/licenses/>.

from uuid import uuid4

from flask import redirect, request, session, url_for
from flask_login import login_required

from .check import check_for_conflicts
from .singletons import app, pg
from .static import propose_pkg_html, propose_whl_html


class Proposal:
    def __init__(self, pg, uuid):
        self.pg = pg
        self.uuid = uuid

    def __iter__(self):
        return (whl for whl, in self.pg.run(
            'SELECT whl FROM proposal WHERE uuid = :uuid',
            uuid=self.uuid))

    def __getitem__(self, pkg):
        return self.pg.run('SELECT whl FROM proposal'
                           ' WHERE uuid = :uuid AND pkg = :pkg',
                           uuid=self.uuid, pkg=pkg)

    def __setitem__(self, pkg, whl):
        self.pg.run('INSERT INTO proposal (uuid, pkg, whl)'
                    ' VALUES (:uuid, :pkg, :whl)'
                    ' ON CONFLICT (uuid, pkg) DO UPDATE SET whl = :whl',
                    uuid=self.uuid, pkg=pkg, whl=whl)

    def set_status(self, conflicts):
        self.pg.run('INSERT INTO autocheck (uuid, conflict)'
                    ' VALUES (:uuid, :conflict)'
                    ' ON CONFLICT (uuid) DO UPDATE SET conflict = :conflict',
                    uuid=self.uuid, conflict=conflicts)


class ProposalCollection:
    def __init__(self, pg):
        self.pg = pg
        self.pg.run('CREATE TEMPORARY TABLE proposal ('
                    ' uuid TEXT, pkg TEXT, whl TEXT,'
                    ' PRIMARY KEY (uuid, pkg))')
        self.pg.run('CREATE TEMPORARY TABLE autocheck ('
                    ' uuid TEXT PRIMARY KEY, conflict BOOL)')

    def __getitem__(self, uuid):
        return Proposal(self.pg, uuid)

    def new(self):
        return self[uuid4().hex]


proposals = ProposalCollection(pg)


def genform(packages):
    for pkg in packages:
        yield f'<input type=text name={pkg} id={pkg} placeholder={pkg}><br>'


@app.route('/propose_pkg', methods=['GET', 'POST'])
@login_required
def propose_pkg():
    if request.method == 'GET': return propose_pkg_html
    session['pkg'] = request.form['pkg'].split(',')
    return redirect(url_for('propose_whl'))


@app.route('/propose_whl', methods=['GET', 'POST'])
@login_required
def propose_whl():
    if request.method == 'GET':
        return propose_whl_html.format(
            ''.join(genform(session['pkg'])))
    proposal = proposals.new()
    for pkg, whl in request.form.items():
        if pkg != 'submit':  # I'm sorry UCSB!
            proposal[pkg] = whl
    try:
        check_for_conflicts(tuple(proposal))
    except ValueError:
        proposal.set_status(conflicts=True)
    else:
        proposal.set_status(conflicts=False)
    return redirect(url_for('index'))
