from rules.dml_no_where import check as check_dml
from rules.select_star import check as check_select_star
from rules.no_pagination import check as check_no_pagination
from rules.sql_injection_classic import check as check_sql_inj
from rules.direct_sensitive import check as check_direct_sensitive
from rules.sql_inconsistent_param import check as check_param


RULES = [
    check_dml,
    check_select_star,
    check_no_pagination,
    check_sql_inj,
    check_direct_sensitive,
    check_param
]