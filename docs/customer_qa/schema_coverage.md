# Покрытие схемы: дамп ≠ полная БД GreenData

**Вывод:** `data_model.sql` — это СРЕЗ. FK ссылаются на 164 таблицы, которых нет в дампе.

## Цифры (воспроизводимо)
```bash
# 60 — CREATE TABLE в файле
grep -c "^CREATE TABLE" data_model_sql/data_model.sql

# 201 — уникальные таблицы в REFERENCES
grep -oP 'REFERENCES public\.\K\w+' data_model_sql/data_model.sql | sort -u | wc -l

# 164 — на которые ссылаются, но которых нет в дампе
comm -13 <(grep -oP 'CREATE TABLE public\.\K\w+' data_model_sql/data_model.sql | sort -u) \
        <(grep -oP 'REFERENCES public\.\K\w+' data_model_sql/data_model.sql | sort -u)
```

| Метрика | Число |
|---|---|
| CREATE TABLE в дампе | 60 |
| Таблиц в REFERENCES | 201 |
| Отсутствуют в дампе | 164 |

## Пример в файле
Строка 17382: `FOREIGN KEY (collateral_id) REFERENCES public.collateral(id)` —
а таблицы `collateral` в дампе нет.

## Вопросы заказчику
1. Сколько таблиц в реальной БД GreenData?
2. Оценка на защите — на этом срезе (60) или на полной схеме?
3. Можно ли получить расширенный срез (хотя бы 164 связанные таблицы)?
4. Где в полной схеме лежат клиенты/ПДн (для настройки DIRECT_SENSITIVE)?

## 60 таблиц в дампе
```
acc_number
afhd_ac_trans_link
application_obj
business_segment
cb_interest_rate
corp_tech_application
count_turnover
credit_contract
dict_div_presence
dict_product
fs_file
ic_application
mler_application
ms_0golbfqyrdq4im6jf6ajivwy9
ms_0n8ohjyx7oszo6a47ca9g0s6f
ms_0oc5mpme8nklimjy77sai9gf1
ms_1fd5jp86pabxu9na4knwphvyr
ms_333s6j5jn97srp008gyi3zueo
ms_39qrctc1n8efr9axiukjssgzl
ms_64cm5ded37z58x0fyt5lgvhc7
ms_965j58mgwkpomnuooc29dlq9f
ms_9k60rv4p0oaf3c702f2l1gj77
ms_d1oakp9uq175ak3dbhpzbu81d
ms_dlggiqkhqj46rhq1lrgryim7c
ms_dxsh6488ihf77xmsd43dwby6k
ms_e5lum3lbateqhx8wkgtstxdf9
offices_psb
participant_app
prod_change_params
prod_commissions
prod_guarantees
product_pricing
scp_amd_product
scp_application
scp_collateral_app
scp_decision_quest
scp_dict_product_na
scp_dict_rsc_office
scp_dict_tech_ctredit
scp_gov_program_dict
scp_part_sec_expertise
scp_prod_comm_dict
scp_prod_guarant_dict
scp_prod_guar_dict
scp_project_ans
scp_sec_check_res
scp_sec_expertise
scp_techcred
sys_algorithm
sys_company
sys_employee
sys_object
sys_obj_resp
sys_obj_type
sys_state
tbs_type
type_loan
yaig_client_gen_agr
yaig_client_guarantee
yaig_product_dict
```

## 164 отсутствующие таблицы (на которые ссылаются FK)
```
account_fields_51
afhd_contract_holder
afhd_credit_report_clas
afhd_gsl_calc_cont
afhd_gsl_data_cont
afhd_prov_part_product
afina_segment_dict
amount_tender_loan
app_pre_aprov_loan
app_pre_aprov_pack_loan
business_segment_dict
chosen_measure
clc_grades
clc_zones
client_group_dict
collateral
collateral_cont
collateral_type_na
comm_date_pay_dict
commissions
credit_report
cr_status
ct_sec_check_res
currency
customer_type
departure
dict_allowed_notallowed
dict_app_status
dict_balance_type
dict_bankruptcy_stage
dict_ckp_risk_zone
dict_comp_sign
dict_contract_group
dict_contracttype
dict_debit_credit
dict_gos_program
dict_group_quality
dict_liquidity_level
dict_loan_form
dict_order_pay_percent
dict_processing_steps
dict_quality_category
dict_scp_risk_zone
dict_source_fininancing
dict_suspension_cd_na
dict_tbs_type_short
dict_yes_no
dict_yes_no_notneeded
directory_collat_object
display_obj_inst
dmm_personal_options
draft_decision
etl_limit_close_na
etl_verification_na
expertise
fs_affil_res_dict
fs_app_aspr_route
fs_bki_res_dict
fs_file_kind
fs_file_type
fs_storage
general_activity_guide
gov_prog_value_dict
group_of_company
guarantee
guarantee_type_dict
interest_penalties
lending_type
link_calc_turn_log
max_amount
mler_decision_quest
number_transactions
overdraft_limit
payment_commission
payment_method
payment_schedule_dict
pay_reward_cond_dict
penalty
pledge_contract
price_formation
pricing_compare
prod_change_param_dict
prod_type_upp_lev
product_compound_dict
product_pricing_cast
product_risk_asses
prof_judjment_indiv
psb_dep_org
quest_structure
rate_type_dict
registration_app
risk_form_inst
risk_form_part_spr
risk_form_row_spr
scp_amd_collateral_type
scp_amd_monit_regul
scp_analys_result_cl
scp_auto_check_trigger
scp_change_comiss_dict
scp_contract_code
scp_dict_appl_type
scp_dict_change_init
scp_dict_client_section
scp_dict_client_type
scp_dict_coll_appl_type
scp_dict_credit_group
scp_dict_industry_code
scp_dict_reason_client
scp_dict_reason_refusal
scp_dict_sec_conclusion
scp_dict_type_req
scp_dict_type_restruct
scp_dict_vnd
scp_gsl_participants
scp_head_cm_decision
scp_loan_sign
scp_matrix_type
scp_modif_lim_quest
scp_proc_steps_dict
scp_purpose_credit
scp_real_estate_class
scp_restruct_initiator
scp_type_gov_prog
scp_type_participant
sex
sf_suppl_check_dict
spr_dyn_type
spr_job_pos
spr_yes_no
standard_fact_app
statement_trans
sum_pay_type_dict
supplemental_aggreement
sys_access_type
sys_alg_card
sys_alg_type
sys_city
sys_company_gsl
sys_content_type
sys_emp_schedule
sys_etl_db_connect
sys_lang_schema
sys_org_str
sys_org_str_view
sys_sec_subject
sys_time_zone
sys_type_attr
sys_user
tbs_items
tech_decision
temp_obj_load_turn
traf_lignts_check_cl
turnover_balance_sheet
type_limit_over
type_of_guarantee
type_payments
underwr_dec_status_dict
underwrit_application
undwrt_decis_level_dict
volume_revenue
wf_document
yaig_client_principal
yaig_gen_agr_type_dict
yaig_guar_type_dict
```
