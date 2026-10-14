import os

app_name = "wheel_tracker"
app_title = "Wheel Tracker"
app_publisher = "Omar Sabry"
app_description = "Diamond/CBN resharpening wheel tracking, wear cost allocation, and reorder alerts for CNC Leaders"
app_email = "omarelgewily2011@gmail.com"
app_license = "mit"


def _v(public_js_path):
	"""Cache-busting query string from the file's own mtime. These JS includes are
	served directly (not through the hashed esbuild bundle pipeline), with a 12-hour
	max-age Cache-Control header — an edit to any of them was otherwise invisible to
	an already-loaded browser for up to 12 hours with no way to tell. Computed at
	import time so it's always correct after any edit with zero manual bumping."""
	fs_path = os.path.join(os.path.dirname(__file__), "public", "js", public_js_path)
	try:
		return f"?v={int(os.path.getmtime(fs_path))}"
	except OSError:
		return ""

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "wheel_tracker",
# 		"logo": "/assets/wheel_tracker/logo.png",
# 		"title": "Wheel Tracker",
# 		"route": "/wheel_tracker",
# 		"has_permission": "wheel_tracker.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/wheel_tracker/css/wheel_tracker.css"
app_include_js = [
	"/assets/wheel_tracker/js/consumption_bar.js" + _v("consumption_bar.js"),
	"/assets/wheel_tracker/js/wheel_tracker_language.js" + _v("wheel_tracker_language.js"),
]

# include js, css files in header of web template
# web_include_css = "/assets/wheel_tracker/css/wheel_tracker.css"
# web_include_js = "/assets/wheel_tracker/js/wheel_tracker.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "wheel_tracker/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# NOTE: doctype_js/doctype_list_js are NOT <script src> tags — Frappe reads these files'
# own content server-side and inlines it into the doctype's meta (as meta.__js/
# meta.__list_js), executed client-side via `new Function(...)`. That server-side read
# resolves the hook's string as a literal filesystem path, so appending `_v()`'s
# `?v=<mtime>` (fine for app_include_js, a real <script src> URL) breaks the path and
# makes the read fail silently — meta.__js/__list_js end up simply unset, no error
# anywhere. Confirmed live: this silently broke image live-preview, the Settings
# reload-after-save, and the consumption bar/color list-view formatters for every page
# load since _v() was added to these two hooks. Never add _v() (or any query string) to
# doctype_js/doctype_list_js values — only app_include_js is a real URL.
doctype_js = {
	"Job Card": "public/js/job_card.js",
	"Wheel Shape": "public/js/shape_image_live_preview.js",
	"Wheel Type": "public/js/shape_image_live_preview.js",
	"Wheel": "public/js/shape_image_live_preview.js",
	"Measurement Event": "public/js/shape_image_live_preview.js",
	"Wheel Retirement": "public/js/shape_image_live_preview.js",
	"Wheel Tracker Settings": "public/js/wheel_tracker_settings.js",
}
doctype_list_js = {
	"Wheel": "public/js/wheel_list.js",
	"Measurement Event": "public/js/measurement_event_list.js",
}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Boot session
# -----------
extend_bootinfo = "wheel_tracker.language_switch.boot_session"

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "wheel_tracker/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "wheel_tracker.utils.jinja_methods",
# 	"filters": "wheel_tracker.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "wheel_tracker.install.before_install"
after_install = "wheel_tracker.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "wheel_tracker.uninstall.before_uninstall"
# after_uninstall = "wheel_tracker.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "wheel_tracker.utils.before_app_install"
# after_app_install = "wheel_tracker.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "wheel_tracker.utils.before_app_uninstall"
# after_app_uninstall = "wheel_tracker.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "wheel_tracker.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

doc_events = {
	"Item": {
		"after_insert": "wheel_tracker.item_variant_hooks.create_wheel_type_from_variant",
	},
	"Stock Entry": {
		"before_validate": "wheel_tracker.stock_entry_hooks.assign_serial_numbers_for_wheel_receipt",
		"on_submit": "wheel_tracker.stock_entry_hooks.create_wheels_on_material_receipt",
	},
	"Stock Ledger Entry": {
		"on_submit": "wheel_tracker.stock_ledger_hooks.sync_wheel_status_from_stock_ledger",
	},
	"Job Card": {
		"validate": "wheel_tracker.job_card_integration.validate_wheel_assignments",
		"on_update": "wheel_tracker.job_card_integration.sync_wheel_assignments",
		"on_trash": "wheel_tracker.job_card_integration.release_wheels_on_trash",
	},
}

# Scheduled Tasks
# ---------------

scheduler_events = {
	"cron": {
		"0 8 * * *": ["wheel_tracker.reorder_alerts.check_reorder_levels"],
	},
}

# Testing
# -------

before_tests = "wheel_tracker.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "wheel_tracker.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "wheel_tracker.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["wheel_tracker.utils.before_request"]
# after_request = ["wheel_tracker.utils.after_request"]

# Job Events
# ----------
# before_job = ["wheel_tracker.utils.before_job"]
# after_job = ["wheel_tracker.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"wheel_tracker.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

