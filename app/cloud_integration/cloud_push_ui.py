"""
cloud_push_ui.py — Streamlit UI component for Talend Cloud push.

Drop-in page rendered inside the Migration Assistant "After" tab or
as a standalone page entry. Lets users:

  1. Enter PAT + region and test connection
  2. Browse their cloud workspace inventory (plans, connections)
  3. Diff cloud inventory vs local migrated jobs
  4. Push plan shells for jobs not yet in the cloud
  5. Open the API portal for binary artifact upload
"""

import streamlit as st
from app.cloud_integration.talend_cloud_client import TalendCloudClient

API_PORTAL_URL = "https://talend.qlik.dev/apis/"


def render_cloud_push_panel(all_jobs: list = None):
    """
    Parameters
    ----------
    all_jobs : list
        The all_jobs list from session_state (job dicts with job_data, etc.).
        If None, the panel still renders but diff and push are disabled.
    """
    st.markdown("### ☁️ Push to Talend Cloud")
    st.info(
        "Connect to your Talend Cloud workspace to diff your migrated jobs "
        "against what already exists and create plan shells for new jobs. "
        "Binary artifact upload uses the Talend Cloud API portal (link below)."
    )

    tab_connect, tab_inventory, tab_diff = st.tabs(
        ["Connect", "Cloud Inventory", "Diff & Push"]
    )

    # ── Tab 1: Credentials ──────────────────────────────────────────────
    with tab_connect:
        with st.container(border=True):
            with st.expander("🔑 Cloud credentials", expanded=True):
                col1, col2 = st.columns([3, 1])
                pat = col1.text_input(
                    "Personal Access Token",
                    type="password",
                    key="cloud_pat",
                    help="Generate in Talend Cloud → Management Console → Personal Access Tokens",
                )
                region = col2.selectbox(
                    "Region", ["us", "eu", "ap", "au"], key="cloud_region"
                )

                if st.button("Test connection", key="cloud_test_btn"):
                    if not pat:
                        st.error("Enter a Personal Access Token first.")
                    else:
                        with st.spinner("Connecting…"):
                            client = TalendCloudClient(pat, region)
                            ok, msg = client.test_connection()
                        if ok:
                            st.success(msg)
                            st.session_state["cloud_client_ok"] = True
                            st.session_state["cloud_pat_val"] = pat
                            st.session_state["cloud_region_val"] = region
                        else:
                            st.error(msg)
                            st.session_state["cloud_client_ok"] = False

            if st.session_state.get("cloud_client_ok"):
                st.caption(
                    f"Connected — region: `{st.session_state.get('cloud_region_val')}`"
                )
            else:
                st.caption("Connect successfully to enable inventory and push.")

    connected = bool(st.session_state.get("cloud_client_ok"))
    client = None
    selected_ws_id = None
    cloud_plan_names = set()
    inventory = None

    if connected:
        client = TalendCloudClient(
            st.session_state["cloud_pat_val"],
            st.session_state["cloud_region_val"],
        )

    # ── Tab 2: Cloud Inventory ───────────────────────────────────────────
    with tab_inventory:
        with st.container(border=True):
            if not connected:
                st.info("Connect in the **Connect** tab first to view cloud inventory.")
            else:
                with st.spinner("Loading workspaces…"):
                    ok_w, workspaces, err_w = client.list_workspaces()

                if not ok_w:
                    st.error(f"Could not load workspaces: {err_w}")
                elif not workspaces:
                    st.warning("No workspaces found for this token. Check TMC permissions.")
                else:
                    ws_names = {
                        ws.get("name", ws.get("id", "?")): ws.get("id", "")
                        for ws in workspaces
                    }
                    selected_ws_name = st.selectbox(
                        "Workspace", list(ws_names.keys()), key="cloud_ws"
                    )
                    selected_ws_id = ws_names[selected_ws_name]

                    st.markdown("#### 📊 Cloud inventory")
                    with st.spinner("Fetching cloud inventory…"):
                        inventory = client.get_migration_inventory(selected_ws_id)

                    cloud_plan_names = {p.get("name", "").lower() for p in inventory["plans"]}

                    col_p, col_c = st.columns(2)
                    col_p.metric("Plans in cloud", inventory["total_plans"])
                    col_c.metric("Connections in cloud", inventory["total_connections"])

                    if inventory["errors"]:
                        for err in inventory["errors"]:
                            st.warning(f"Partial inventory error: {err}")

                    with st.expander("View cloud plans"):
                        if inventory["plans"]:
                            st.dataframe(
                                [
                                    {"name": p.get("name"), "id": p.get("id"), "status": p.get("status")}
                                    for p in inventory["plans"]
                                ],
                                width="stretch",
                                hide_index=True,
                            )
                        else:
                            st.caption("No plans found in this workspace.")

    # ── Tab 3: Diff & Push ────────────────────────────────────────────────
    with tab_diff:
        with st.container(border=True):
            if not connected:
                st.info("Connect in the **Connect** tab first to enable diff and push.")
            elif inventory is None:
                st.info("Select a workspace in the **Cloud Inventory** tab first.")
            elif not all_jobs:
                st.info("Run Repository Intake analysis first to enable diff and push.")
                if st.button("Go to Repository Intake", key="cloud_goto_intake"):
                    st.session_state["wizard_step"] = 1
                    st.rerun()
            else:
                local_job_names = [j["job_data"]["job_name"] for j in all_jobs]
                missing_in_cloud = [n for n in local_job_names if n.lower() not in cloud_plan_names]
                already_in_cloud = [n for n in local_job_names if n.lower() in cloud_plan_names]

                st.markdown("#### Local vs cloud diff")
                col_m, col_a = st.columns(2)
                col_m.metric("Jobs not yet in cloud", len(missing_in_cloud), delta_color="inverse")
                col_a.metric("Jobs already in cloud", len(already_in_cloud))

                if missing_in_cloud:
                    with st.expander(f"Jobs missing in cloud ({len(missing_in_cloud)})"):
                        for name in missing_in_cloud:
                            st.markdown(f"- `{name}`")

                if already_in_cloud:
                    with st.expander(f"Jobs already in cloud ({len(already_in_cloud)})"):
                        for name in already_in_cloud:
                            st.markdown(f"- `{name}`")

                if missing_in_cloud:
                    st.markdown("#### Push plan shells")
                    st.caption(
                        "Creates a plan record in Talend Cloud for each missing job. "
                        "Bind the compiled artifact afterwards via the API portal (link below)."
                    )

                    selected_to_push = st.multiselect(
                        "Select jobs to push",
                        missing_in_cloud,
                        default=missing_in_cloud[:5],
                        key="cloud_push_select",
                    )

                    if st.button("Push selected to cloud", key="cloud_push_btn", type="primary"):
                        if not selected_to_push:
                            st.warning("Select at least one job to push.")
                        else:
                            results = []
                            with st.status(
                                "Pushing jobs to Talend Cloud…", expanded=True
                            ) as status:
                                for job_name in selected_to_push:
                                    ok, plan, err = client.publish_job_as_plan(
                                        job_name=job_name,
                                        workspace_id=selected_ws_id,
                                    )
                                    label = "Created" if ok else f"Failed: {err}"
                                    st.write(f"{job_name}: {label}")
                                    results.append({
                                        "job": job_name,
                                        "success": ok,
                                        "status": label,
                                        "plan_id": plan.get("id", "") if ok else "",
                                    })
                                all_ok = all(r["success"] for r in results)
                                status.update(
                                    label="Push complete" if all_ok else "Push finished with errors",
                                    state="complete" if all_ok else "error",
                                )

                            st.dataframe(results, width="stretch", hide_index=True)
                            pushed = sum(1 for r in results if r["success"])
                            st.success(f"Pushed {pushed}/{len(selected_to_push)} plan shells to Talend Cloud.")

    st.caption("Next step: upload compiled job artifacts via the Talend Cloud API portal.")
    st.link_button("Open API portal", API_PORTAL_URL)
