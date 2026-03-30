;;; RepoMap Python tree-sitter query
;;; Extracts: functions, async functions, classes, methods, imports, calls,
;;;           Pydantic models, dataclasses, decorators, entry points.

;;; ─── Top-level function definitions ─────────────────────────────────────────
(function_definition
  name: (identifier) @def.function.name
  parameters: (parameters) @def.function.params
  return_type: (type)? @def.function.return_type) @def.function

;;; ─── Async function definitions ──────────────────────────────────────────────
(decorated_definition
  (decorator) @def.function.decorator
  definition: (function_definition
    name: (identifier) @def.function.name
    parameters: (parameters) @def.function.params
    return_type: (type)? @def.function.return_type)) @def.function.decorated

;;; ─── Class definitions ───────────────────────────────────────────────────────
(class_definition
  name: (identifier) @def.class.name
  superclasses: (argument_list)? @def.class.bases) @def.class

;;; ─── Method definitions ───────────────────────────────────────────────────────
(class_definition
  body: (block
    (function_definition
      name: (identifier) @def.method.name
      parameters: (parameters) @def.method.params
      return_type: (type)? @def.method.return_type) @def.method))

;;; ─── Decorated methods ────────────────────────────────────────────────────────
(class_definition
  body: (block
    (decorated_definition
      (decorator) @def.method.decorator
      definition: (function_definition
        name: (identifier) @def.method.name
        parameters: (parameters) @def.method.params
        return_type: (type)? @def.method.return_type) @def.method.decorated_inner)))

;;; ─── Import statements ───────────────────────────────────────────────────────
(import_statement
  name: (dotted_name) @ref.import.module) @ref.import

(import_from_statement
  module_name: (dotted_name)? @ref.import.from_module
  name: [(dotted_name) (aliased_import)] @ref.import.name) @ref.import.from

;;; ─── Function call references ────────────────────────────────────────────────
(call
  function: (identifier) @ref.call.name) @ref.call.simple

(call
  function: (attribute
    object: (_) @ref.call.object
    attribute: (identifier) @ref.call.name)) @ref.call.attr
