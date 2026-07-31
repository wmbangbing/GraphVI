# Neo4j 图 Schema

> 导出时间: 2026-07-24
> 连接地址: bolt://10.3.72.74:7688

## 节点属性

### dm_dispatch_apply

  - `address`: String
  - `apply_person_tel`: String
  - `apply_person`: String
  - `apply_type`: String
  - `apply_unit_name`: String
  - `audit_status`: String
  - `city`: String
  - `collection_place`: String
  - `contact_person_phone`: String
  - `contact_person`: String
  - `county`: String
  - `event_id`: String
  - `id`: String
  - `latitude`: Double
  - `longitude`: Double
  - `pac`: String
  - `province`: String
  - `req_submission_time`: String
  - `task_guarantee_end_time`: String
  - `task_guarantee_start_time`: String
  - `task_requirements`: String
  - `urgent_level`: String

### dm_dispatch_equipment

  - `call_record`: String
  - `equipment_code`: String
  - `equipment_mac_addr`: String
  - `equipment_name`: String
  - `equipment_num`: Long
  - `equipment_status`: String
  - `equipment_sub_second_type`: String
  - `equipment_sub_type`: String
  - `equipment_type`: String
  - `equipment_used_flow`: String
  - `id`: String
  - `is_recall`: String
  - `latest_latitude`: Double
  - `latest_longitude`: Double
  - `ref_equipment_id`: String
  - `satellite_phone`: String
  - `spec_model`: String
  - `task_id`: String

### dm_dispatch_person

  - `id`: String
  - `is_recall`: String
  - `major`: String
  - `name`: String
  - `person_status`: String
  - `phone`: String
  - `political_status`: String
  - `ref_person_id`: String
  - `ship_license`: String
  - `task_id`: String
  - `uav_license`: String
  - `vehicle_license`: String

### dm_dispatch_process_record

  - `address`: String
  - `apply_id`: String
  - `handle_time`: String
  - `id`: String
  - `latitude`: Double
  - `longitude`: Double
  - `member_id`: String
  - `org_code`: String
  - `org_name`: String
  - `process_content`: String
  - `process_record_type`: String
  - `remark_info`: String
  - `task_id`: String
  - `user_name`: String

### dm_dispatch_record_info

  - `id`: String
  - `is_recall`: String
  - `relate_id`: String
  - `resource_num`: Long
  - `task_id`: String

### dm_dispatch_task

  - `apply_id`: String
  - `datasources`: String
  - `distribute_status`: String
  - `execute_dept_name`: String
  - `gather_location`: String
  - `id`: String
  - `pac`: String
  - `task_code`: String
  - `task_require`: String
  - `task_status`: String
  - `team_leader_name`: String
  - `team_leader_phone`: String

### dm_dispatch_vehicle

  - `business_capability`: String
  - `id`: String
  - `is_recall`: String
  - `latest_latitude`: Double
  - `latest_longitude`: Double
  - `plate_no`: String
  - `ref_vehicle_id`: String
  - `task_id`: String
  - `vehicle_name`: String
  - `vehicle_param`: String
  - `vehicle_status`: String
  - `vehicle_type`: String

### dm_equipment_info

  - `address`: String
  - `brand`: String
  - `call_record`: String
  - `charter_person_phone`: String
  - `charter_person`: String
  - `equipment_code`: String
  - `equipment_name`: String
  - `equipment_status`: String
  - `equipment_sub_second_type`: String
  - `equipment_sub_type`: String
  - `equipment_type`: String
  - `equipment_used_flow`: String
  - `id`: String
  - `ka_modem_mac`: String
  - `ku_modem_sn`: String
  - `latitude`: Double
  - `local_city`: String
  - `local_province`: String
  - `longitude`: Double
  - `model`: String
  - `pac`: String
  - `satellite_phone`: String
  - `updatetime`: String

### dm_event_bxz_device_flow

  - `cpe_id`: String
  - `cpe_mac_str`: String
  - `cpe_mac`: String
  - `delete_flag`: String
  - `end_collection_time`: String
  - `flow_id`: String
  - `forward_throughput`: String
  - `ins_time`: String
  - `reverse_throughput`: String
  - `start_collection_time`: String
  - `total_throughput`: String

### dm_event_duty_procinfo

  - `alert_level`: String
  - `alert_type`: String
  - `close_operator_name`: String
  - `close_operator_time`: String
  - `command_dispatch`: String
  - `content`: String
  - `del_flag`: Boolean
  - `event_id`: String
  - `id`: String
  - `is_transferred_to_event`: String
  - `level`: String
  - `material_preset`: String
  - `net_alarm_type`: String
  - `pac`: String
  - `publish_time`: String
  - `rainfall_12h`: String
  - `rainfall_6h`: String
  - `status`: String
  - `task_number`: String
  - `title`: String
  - `type`: String
  - `updated_at`: String
  - `warning_analysis`: String
  - `warning_id`: String
  - `weather_content`: String

### dm_event_info

  - `area_of_impact_code`: String
  - `create_org_name`: String
  - `event_code`: String
  - `event_desc`: String
  - `event_end_time`: String
  - `event_level`: String
  - `event_name`: String
  - `event_occur_time`: String
  - `event_source`: String
  - `event_type`: String
  - `id`: String
  - `is_main_event`: String
  - `pac`: String
  - `relate_event_code`: String
  - `response_level`: String
  - `response_org`: String
  - `response_time`: String
  - `status`: String
  - `three_break`: String

### dm_person_info

  - `city`: String
  - `expert_level_code`: String
  - `id`: String
  - `is_low_voltage`: String
  - `multirotor_certification`: String
  - `pac`: String
  - `person_name`: String
  - `person_no`: String
  - `person_status`: String
  - `phone`: String
  - `political_status`: String
  - `province`: String
  - `ship_license`: String
  - `specialty_skill`: String
  - `uav_license`: String
  - `unit`: String
  - `updatetime`: String
  - `vehicle_license`: String

### dm_tt_dsj_call

  - `end_time`: String
  - `id`: String
  - `ins_time`: String
  - `phone`: String
  - `r_phone`: String
  - `start_time`: String
  - `sub_evt_type`: String
  - `upd_time`: String

### dm_vehicle_info

  - `address`: String
  - `brand`: String
  - `business_capability`: String
  - `car_id`: String
  - `category_child_code`: String
  - `city`: String
  - `id`: String
  - `latitude`: Double
  - `longitude`: Double
  - `name_a`: String
  - `pac`: String
  - `phone_a`: String
  - `plate_no`: String
  - `province`: String
  - `status`: String
  - `transmission_capability_code`: String
  - `updatetime`: String
  - `vehicle_code_num`: Long
  - `vehicle_name`: String
  - `vehicle_type`: String

### dm_weather_warning_data

  - `d_datetime`: String
  - `data_id`: String
  - `id`: String
  - `rel_id`: String
  - `senderlevel`: String
  - `title`: String
  - `updatetime`: String
  - `v_expires`: String
  - `v_issuecontent`: String
  - `v_sender`: String
  - `v_senderareacode`: String
  - `v_signallevel`: String
  - `v_signaltype`: String
  - `v_underwriter`: String

### dm_work_order

  - `alert_level`: String
  - `alert_type`: String
  - `event_id`: String
  - `event_operator_name`: String
  - `event_operator_time`: String
  - `id`: String
  - `is_trans_event`: String
  - `level`: String
  - `pac`: String
  - `publish_time`: String
  - `task_code`: String
  - `work_order_content`: String
  - `work_order_name`: String
  - `work_order_status`: String
  - `work_order_type`: String

### qxyj_DisasterType

  - `typecode`: String
  - `typename`: String

### qxyj_DispatchPlan

  - `area_level`: String
  - `disaster_code`: String
  - `event_level`: String
  - `plan_id`: String
  - `province`: String
  - `status`: String
  - `type_l1`: String
  - `type_l2`: String
  - `type_l3`: String

### qxyj_HistoryDetail

  - `event_id`: String
  - `id`: String
  - `material_num`: Long
  - `resource_type`: String

### qxyj_HistoryDispatch

  - `event_id`: String
  - `event_level`: String
  - `event_type`: String
  - `id`: String
  - `occur_time`: String
  - `pac`: String
  - `title`: String

### qxyj_PlanDetail

  - `detail_id`: String
  - `plan_id`: String
  - `recommend_num`: String
  - `resource_type`: String

### qxyj_ResourceType

  - `category_l1`: String
  - `category_l2`: String
  - `resource_name`: String
  - `resource_type`: String

### qxyj_district_ec

  - `area_level`: String
  - `districtname`: String
  - `full_name`: String
  - `latitude`: Double
  - `longitude`: Double
  - `pac`: String
  - `parentcode`: String

### qxyj_ec_vehicle

  - `address`: String
  - `brand`: String
  - `category_code`: String
  - `id`: String
  - `latitude`: Double
  - `longitude`: Double
  - `name`: String
  - `pac`: String
  - `plateno`: String
  - `resource_type`: String
  - `status`: String
  - `vehtype`: String

### qxyj_equipment

  - `address`: String
  - `brand`: String
  - `id`: String
  - `model`: String
  - `pac`: String
  - `resource_type`: String
  - `status`: String
  - `type_flag`: String
  - `vehtype`: String

### qxyj_weather_warning_type

  - `disaster_code`: String
  - `parentcode`: String
  - `typecode`: String
  - `typename`: String

### sys_attachment

  - `create_user`: String
  - `file_size`: Long
  - `file_type`: String
  - `id`: String
  - `old_name`: String
  - `path`: String
  - `ref_id`: String

## 关系属性

### APPLY_GENERATE_DISPATCH_TASK

  - `None`: ANY

### DISPATCH_RECORD_RELATE_EQUIPMENT

  - `None`: ANY

### DISPATCH_RECORD_RELATE_PERSON

  - `None`: ANY

### DISPATCH_RECORD_RELATE_VEHICLE

  - `None`: ANY

### EVENT_TRIGGER_DISPATCH_APPLY

  - `None`: ANY

### PARENT_OF

  - `None`: ANY

### QXYJ_APPLY_TO

  - `None`: ANY

### QXYJ_BELONG_DISASTERTYPE

  - `None`: ANY

### QXYJ_EQUIPMENT_BELONG_TYPE

  - `None`: ANY

### QXYJ_EQUIPMENT_LOCATED_AT

  - `None`: ANY

### QXYJ_HAPPEN_IN

  - `None`: ANY

### QXYJ_HIST_USE

  - `None`: ANY

### QXYJ_LINK_HIST

  - `None`: ANY

### QXYJ_LINK_PLAN

  - `None`: ANY

### QXYJ_RECOMMEND

  - `None`: ANY

### QXYJ_VEHICLE_BELONG_TYPE

  - `None`: ANY

### QXYJ_VEHICLE_LOCATED_AT

  - `None`: ANY

### QXYJ_WARNING_LINK_DISASTER

  - `None`: ANY

### RECORD_ATTACH_ATTACHMENT

  - `None`: ANY

### TASK_BIND_PROCESS_RECORD

  - `None`: ANY

### TASK_GEN_DISPATCH_RECORD

  - `None`: ANY

### WORKORDER_RELATE_EVENT

  - `None`: ANY

## 关系模式

  - `(:dm_dispatch_apply)-[:APPLY_GENERATE_DISPATCH_TASK]->(:dm_dispatch_task)`
  - `(:dm_dispatch_process_record)-[:RECORD_ATTACH_ATTACHMENT]->(:sys_attachment)`
  - `(:dm_dispatch_record_info)-[:DISPATCH_RECORD_RELATE_EQUIPMENT]->(:dm_equipment_info)`
  - `(:dm_dispatch_record_info)-[:DISPATCH_RECORD_RELATE_PERSON]->(:dm_person_info)`
  - `(:dm_dispatch_record_info)-[:DISPATCH_RECORD_RELATE_VEHICLE]->(:dm_vehicle_info)`
  - `(:dm_dispatch_task)-[:TASK_BIND_PROCESS_RECORD]->(:dm_dispatch_process_record)`
  - `(:dm_dispatch_task)-[:TASK_GEN_DISPATCH_RECORD]->(:dm_dispatch_record_info)`
  - `(:dm_event_info)-[:EVENT_TRIGGER_DISPATCH_APPLY]->(:dm_dispatch_apply)`
  - `(:dm_event_info)-[:PARENT_OF]->(:dm_event_info)`
  - `(:dm_work_order)-[:WORKORDER_RELATE_EVENT]->(:dm_event_info)`
  - `(:qxyj_DispatchPlan)-[:QXYJ_APPLY_TO]->(:qxyj_district_ec)`
  - `(:qxyj_DispatchPlan)-[:QXYJ_BELONG_DISASTERTYPE]->(:qxyj_DisasterType)`
  - `(:qxyj_DispatchPlan)-[:QXYJ_LINK_PLAN]->(:qxyj_PlanDetail)`
  - `(:qxyj_HistoryDetail)-[:QXYJ_HIST_USE]->(:qxyj_ResourceType)`
  - `(:qxyj_HistoryDetail)-[:QXYJ_LINK_HIST]->(:qxyj_HistoryDispatch)`
  - `(:qxyj_HistoryDispatch)-[:QXYJ_HAPPEN_IN]->(:qxyj_district_ec)`
  - `(:qxyj_PlanDetail)-[:QXYJ_RECOMMEND]->(:qxyj_ResourceType)`
  - `(:qxyj_ec_vehicle)-[:QXYJ_VEHICLE_BELONG_TYPE]->(:qxyj_ResourceType)`
  - `(:qxyj_ec_vehicle)-[:QXYJ_VEHICLE_LOCATED_AT]->(:qxyj_district_ec)`
  - `(:qxyj_equipment)-[:QXYJ_EQUIPMENT_BELONG_TYPE]->(:qxyj_ResourceType)`
  - `(:qxyj_equipment)-[:QXYJ_EQUIPMENT_LOCATED_AT]->(:qxyj_district_ec)`
  - `(:qxyj_weather_warning_type)-[:QXYJ_WARNING_LINK_DISASTER]->(:qxyj_DisasterType)`
