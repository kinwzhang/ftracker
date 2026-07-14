# Security Scan Report - XSS & DOM Code Injection
**Date:** 2026-07-14
**Scan Result:** 2 Stored XSS, 6 Client DOM Stored Code Injection, 6 Client DOM Code Injection
**Branch:** fix/xss-security-scan

---

## Summary

| Category | Count | Severity | Status |
|----------|-------|----------|--------|
| Stored XSS | 2 | HIGH | Fixed |
| Client DOM Stored Code Injection | 6 | HIGH | Fixed |
| Client DOM Code Injection | 6 | MEDIUM | Fixed |
| **Total** | **14** | | **All Fixed** |

---

## 1. Stored XSS (2 Instances)

### Instance 1.1: Unsafe JSON Serialization in Template
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_form.html:82` |
| **Type** | Stored XSS |
| **Severity** | HIGH |
| **Vulnerable Code** | `const templates = {{ templates_json\|safe }};` |
| **Risk** | User-controlled `task_name` or `assigned_to` fields containing `</script>` or HTML entities could break out of the script context and execute arbitrary JavaScript |
| **Fix** | Replaced with Django's `json_script` filter which safely escapes JSON for HTML embedding |
| **Fixed Code** | `const templates = {{ templates_json\|json_script:"templates-data" }};` + `JSON.parse(document.getElementById('templates-data').textContent)` |
| **View Change** | `views.py:361` - Changed from `json.dumps()` to Python list for `json_script` filter compatibility |

### Instance 1.2: User Data in JavaScript confirm() Dialog
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/template_list.html:47,132,140` |
| **Type** | Stored XSS |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `onsubmit="return confirm('Delete group {{ g.name }}?...')"` |
| **Risk** | Group or template names containing single quotes or HTML could break out of the JavaScript string context in the `onsubmit` attribute |
| **Fix** | Removed user data from `confirm()` dialogs, replaced with generic messages |
| **Fixed Code** | `onsubmit="return confirm('Delete this group?...')"` |

---

## 2. Client DOM Stored Code Injection (6 Instances)

### Instance 2.1: innerHTML in Comment Save Handler
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:647` |
| **Type** | Client DOM Stored Code Injection |
| **Severity** | HIGH |
| **Vulnerable Code** | `display.innerHTML = data.comments ? ... : '<span class="text-muted">...</span>';` |
| **Risk** | Server-returned comment text injected directly into DOM via `innerHTML` could contain malicious HTML/JS that executes in the user's browser |
| **Fix** | Replaced `innerHTML` with `textContent` for plain text and DOM API for HTML structure |
| **Fixed Code** | Uses `document.createElement()`, `textContent`, and `appendChild()` |

### Instance 2.2: innerHTML in Count Update Function
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:521` |
| **Type** | Client DOM Stored Code Injection |
| **Severity** | HIGH |
| **Vulnerable Code** | `span.innerHTML = '<strong>' + n + '</strong> ' + COUNT_LABELS[key];` |
| **Risk** | Count labels concatenated into HTML string and injected via `innerHTML` could be manipulated if count values are tampered with |
| **Fix** | Replaced `innerHTML` with DOM creation methods, added `while(span.firstChild) span.removeChild(span.firstChild)` to clear existing content before appending |
| **Fixed Code** | Uses `document.createElement('strong')`, `textContent`, and `appendChild()` with content clearing |

### Instance 2.3: title Attribute with Task Name (Gantt Label)
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:121` |
| **Type** | Client DOM Stored Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `title="{{ gt.task.task_name }} ({{ gt.task.scheduled_date }})"` |
| **Risk** | Task names in title attributes could contain characters that break attribute context |
| **Fix** | Added explicit `\|escape` filter |
| **Fixed Code** | `title="{{ gt.task.task_name\|escape }} ({{ gt.task.scheduled_date }})"` |

### Instance 2.4: title Attribute with Task Name (Gantt Bar)
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:125` |
| **Type** | Client DOM Stored Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `title="{{ gt.task.task_name }} - Due: {{ gt.task.scheduled_date }}"` |
| **Risk** | Task names in title attributes could contain characters that break attribute context |
| **Fix** | Added explicit `\|escape` filter |
| **Fixed Code** | `title="{{ gt.task.task_name\|escape }} - Due: {{ gt.task.scheduled_date\|date:\"Y-m-d\" }}"` |

### Instance 2.5: title Attribute with Group Name
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:97` |
| **Type** | Client DOM Stored Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `title="{{ block.group.name\|default:'Ungrouped' }} — ..."` |
| **Risk** | Group names in title attributes could contain characters that break attribute context |
| **Fix** | Added explicit `\|escape` filter |
| **Fixed Code** | `title="{{ block.group.name\|default:\"Ungrouped\"\|escape }} — ..."` |

### Instance 2.6: readable_message() in Dashboard
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/dashboard.html:102` |
| **Type** | Client DOM Stored Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `{{ log.readable_message }}` |
| **Risk** | Audit log messages containing user data (task names, old/new values) could contain malicious HTML |
| **Fix** | Added explicit `\|escape` filter for defense-in-depth |
| **Fixed Code** | `{{ log.readable_message\|escape }}` |

---

## 3. Client DOM Code Injection (6 Instances)

### Instance 3.1: Task Name in Task List View
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:184-185` |
| **Type** | Client DOM Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `<span class="view-mode">{{ task.task_name }}</span>` and `value="{{ task.task_name }}"` |
| **Risk** | Task names rendered in HTML elements without explicit escaping |
| **Fix** | Added `\|escape` filter to all task name outputs |
| **Fixed Code** | `{{ task.task_name\|escape }}` |

### Instance 3.2: Assigned To in Task List View
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:188-189` |
| **Type** | Client DOM Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `<span class="view-mode">{{ task.assigned_to }}</span>` and `value="{{ task.assigned_to }}"` |
| **Risk** | Assigned-to names rendered in HTML elements without explicit escaping |
| **Fix** | Added `\|escape` filter |
| **Fixed Code** | `{{ task.assigned_to\|escape }}` |

### Instance 3.3: Comments in Task List View
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:212-213` |
| **Type** | Client DOM Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `{{ task.comments\|truncatechars:20 }}` and `value="{{ task.comments }}"` |
| **Risk** | Comments rendered in HTML elements without explicit escaping |
| **Fix** | Added `\|escape` filter |
| **Fixed Code** | `{{ task.comments\|truncatechars:20\|escape }}` and `value="{{ task.comments\|escape }}"` |

### Instance 3.4: Group Name in Task List View
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/task_list.html:216,220` |
| **Type** | Client DOM Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `{{ task.group.name }}` and `{{ g.name }}` in select options |
| **Risk** | Group names rendered in HTML elements without explicit escaping |
| **Fix** | Added `\|escape` filter |
| **Fixed Code** | `{{ task.group.name\|escape }}` and `{{ g.name\|escape }}` |

### Instance 3.5: Task Data in Export Report
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/export_report.html:37-44` |
| **Type** | Client DOM Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `{{ task.task_name }}`, `{{ task.assigned_to }}`, `{{ task.comments }}` |
| **Risk** | Task data rendered in HTML table cells without explicit escaping |
| **Fix** | Added `\|escape` filter to all user-data fields |
| **Fixed Code** | `{{ task.task_name\|escape }}`, `{{ task.assigned_to\|escape }}`, `{{ task.comments\|escape }}` |

### Instance 3.6: Audit Log in Export Report
| Field | Value |
|-------|-------|
| **File** | `tracker/templates/tracker/export_report.html:61` |
| **Type** | Client DOM Code Injection |
| **Severity** | MEDIUM |
| **Vulnerable Code** | `{{ log.readable_message }}` |
| **Risk** | Audit log messages containing user data rendered without explicit escaping |
| **Fix** | Added `\|escape` filter |
| **Fixed Code** | `{{ log.readable_message\|escape }}` |

---

## 4. Additional Defense-in-Depth Fixes

The following user-data outputs were also hardened with explicit `|escape` filters:

| File | Line | Output |
|------|------|--------|
| `task_list.html:90` | `{{ block.group.name\|default:"Ungrouped"\|escape }}` | Gantt group label |
| `task_list.html:169` | `{{ block.group.name\|default:"Ungrouped"\|escape }}` | Table group summary |
| `template_list.html:37-38` | `{{ g.name\|escape }}` | Group name view/input |
| `template_list.html:102-103` | `{{ tmpl.task_name\|escape }}` | Template name view/input |
| `template_list.html:106-107` | `{{ tmpl.assigned_to\|escape }}` | Template assigned-to view/input |
| `template_list.html:121` | `{{ tmpl.group.name\|escape }}` | Template group name |
| `template_list.html:125` | `{{ g.name\|escape }}` | Group select options |
| `task_form.html:12` | `{{ task.task_name\|default:''\|escape }}` | Task form name input |
| `task_form.html:16` | `{{ task.assigned_to\|default:''\|escape }}` | Task form assigned-to input |
| `task_form.html:45` | `{{ g.name\|escape }}` | Task form group select |
| `task_form.html:51` | `{{ task.comments\|default:''\|escape }}` | Task form comments textarea |
| `task_form.html:70-71` | `{{ t.task_name\|escape }}`, `{{ t.assigned_to\|escape }}` | Template quick-add table |
| `template_form.html:12` | `{{ tmpl.task_name\|default:''\|escape }}` | Template form name input |
| `template_form.html:16` | `{{ tmpl.assigned_to\|default:''\|escape }}` | Template form assigned-to input |
| `template_form.html:38` | `{{ g.name\|escape }}` | Template form group select |

---

## 5. Files Modified

| File | Changes |
|------|---------|
| `tracker/templates/tracker/task_list.html` | Replaced innerHTML with textContent/DOM, added escape filters |
| `tracker/templates/tracker/task_form.html` | Replaced \|safe with json_script, added escape filters |
| `tracker/templates/tracker/template_list.html` | Removed user data from confirm(), added escape filters |
| `tracker/templates/tracker/template_form.html` | Added escape filters |
| `tracker/templates/tracker/dashboard.html` | Added escape filter to audit logs |
| `tracker/templates/tracker/export_report.html` | Added escape filters to task data and audit logs |
| `tracker/views.py` | Changed templates_json from json.dumps() to Python list |

---

## 6. Testing

- All 74 existing unit tests pass
- No regressions introduced

---

## 7. Recommendations

1. **Enable Django's auto-escape globally** (already enabled by default) - ensure `{% autoescape off %}` is never used with user data
2. **Use Content Security Policy (CSP) headers** to provide additional protection against XSS
3. **Regular security scans** - Schedule monthly scans to catch new vulnerabilities
4. **Input validation** - Consider adding server-side validation for task_name, assigned_to, and comments fields to restrict allowed characters
5. **Consider using Django's `mark_safe()` carefully** - Never use with user-controlled data
