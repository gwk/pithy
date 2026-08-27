# Dedicated to the public domain under CC0: https://creativecommons.org/publicdomain/zero/1.0/.

from pithy.web.dbview import TableAbbrs
from pithy.web.dbview.vis import Vis
from utest import utest, utest_val


utest({'main':''}, TableAbbrs.abbreviate_schema_names, {'main'})
utest({'main':'ma', 'meta':'me'}, TableAbbrs.abbreviate_schema_names, {'main', 'meta'})
utest({'a':'a', 'b':'b'}, TableAbbrs.abbreviate_schema_names, {'a', 'b'})


abbrs = TableAbbrs(schema='main', table='Primary', all_vis=[Vis(show=True), Vis(key='main.Users.id', col='name')])
#^ Non-key Vis entries must not contribute an empty schema name.
utest_val('P', abbrs.table_abbr)

utest('UE', abbrs.unique_abbr, 'main', 'UserEvent')
utest('UE1', abbrs.unique_abbr, 'main', 'UnitEstimate')
utest('UE2', abbrs.unique_abbr, 'main', 'UserEvent')
utest('ue3', abbrs.unique_abbr, 'main', 'user_event') # Lowercase names use word initials; collisions are case-insensitive.
utest('u', abbrs.unique_abbr, 'main', 'users')
utest('IS0', abbrs.unique_abbr, 'main', 'Inner Select') # Keyword abbreviation gets a 0 suffix.
utest('IS1', abbrs.unique_abbr, 'main', 'Item Set')
utest('as0', abbrs.unique_abbr, 'main', 'address_state')
