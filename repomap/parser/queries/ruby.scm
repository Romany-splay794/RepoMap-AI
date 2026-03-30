;;; RepoMap Ruby tree-sitter query
;;; Extracts: methods, singleton methods, classes, modules, imports, calls.

;;; ─── Method definitions ─────────────────────────────────────────────────────
(method
  name: (identifier) @def.function.name
  parameters: (method_parameters)? @def.function.params) @def.function

;;; ─── Singleton (class) methods ──────────────────────────────────────────────
(singleton_method
  object: (_) @def.method.receiver
  name: (identifier) @def.method.name
  parameters: (method_parameters)? @def.method.params) @def.method

;;; ─── Class definitions ──────────────────────────────────────────────────────
(class
  name: (constant) @def.class.name
  superclass: (superclass)? @def.class.bases) @def.class

;;; ─── Module definitions ─────────────────────────────────────────────────────
(module
  name: (constant) @def.class.name) @def.class

;;; ─── Require/import statements ──────────────────────────────────────────────
(call
  method: (identifier) @_require_method
  arguments: (argument_list
    (string) @ref.import.source)
  (#match? @_require_method "^require"))  @ref.import

;;; ─── Function call references ───────────────────────────────────────────────
(call
  method: (identifier) @ref.call.name) @ref.call.simple

(call
  receiver: (_) @ref.call.object
  method: (identifier) @ref.call.name) @ref.call.attr
