"""Build CP3's document-derived taxonomy before looking at corpus contents."""
import hashlib, json, re
from pathlib import Path
BASE=Path("compile_repair/artifacts/cp3_v1")
DOCS=Path("/home/zhao/SmartContract/corpora")
definitions=[
("unresolved_package_import","IOError,ParserError","Source <path> not found","Package is absent or no supplied mapping resolves its source-unit name.","deterministic: authorized offline package and version match; otherwise agent after dependency evidence","additive","delete an imported package file"),
("missing_relative_file","IOError,ParserError","Source <path> not found","Relative import target is absent from the approved project.","deterministic only with an unambiguous identity-checked existing dependency; otherwise agent","additive","delete or rename a relative dependency"),
("undeclared_identifier","DeclarationError","Undeclared identifier|Identifier not found","A referenced declaration or scope is missing.","deterministic declaration-only stub when its complete type is constrained; otherwise agent","additive","delete a referenced declaration"),
("missing_base_contract","DeclarationError","Identifier not found or not unique|Definition of base has to precede","A base declaration is absent, ambiguous, or ordered incorrectly.","deterministic proven declaration recovery; otherwise agent","additive","delete a base contract"),
("duplicate_definition","DeclarationError","Identifier already declared|defined twice|same name and parameter types","Flattening or project assembly introduced competing declarations.","deterministic only for byte/token-identical declarations with preserved binding; otherwise agent","rewrite","duplicate a declaration"),
("multiple_license_or_pragma","ParserError,SyntaxError","Multiple SPDX license identifiers|ABI coder has already been selected|experimental features","Repeated flattened directives may conflict; repeated Solidity constraints alone are not inherently invalid.","deterministic redundant identical directive removal only; conflicting licenses require human scope decision and conflicting versions require evidence","rewrite","duplicate a license or ABI-coder directive"),
("encoding","ParserError","Invalid character|Invalid escape|Invalid UTF-8|unicode","Bytes or escapes are not legal at their lexical position; arbitrary comment bytes need not fail.","deterministic BOM or proven escape representation correction; otherwise agent","rewrite","insert an illegal token byte or escape"),
("unbalanced_structure","ParserError","Expected token Semicolon got 'RBrace'|Expected ';' but got '}'|end of source","A required delimiter, statement terminator, or source tail is missing.","deterministic unique missing delimiter with no invented executable body; otherwise agent","additive","delete a delimiter or truncate a declaration"),
("parser_error_other","ParserError","Expected <token> but got <token>|Expected token","Grammar does not accept the token sequence.","deterministic documented local syntax migration where equivalent; otherwise agent","rewrite","replace a valid token with an invalid token"),
("type_error_other","TypeError","not implicitly convertible|Invalid type|Wrong argument count|Member <name> not found","Declarations and expressions have incompatible types or arity.","deterministic mechanically equivalent type spelling or cast only; otherwise agent","rewrite","change a parameter or expression type"),
("codegen_only","CompilerError,UnimplementedFeatureError","Stack too deep|stack too deep|Unimplemented feature","Parsing/type checking succeeded but requested code generation cannot finish.","deterministic compiler settings only after matched solc and Slither D3 validation; otherwise tool limitation","none","extend a function with simultaneously live values"),
("closure_version_conflict","SyntaxError","F: empty pragma interval","File constraints or their transitive intersection have no common compiler.","deterministic compatible original dependency retrieval only; otherwise agent with version evidence","additive","change dependency pragma to a disjoint interval"),
("slither_incomplete",None,"solc rc0; Slither exception or D3(a/b) incomplete","Analysis cannot represent the compiler-accepted unit.","deterministic only for separately proven equivalent tuple-call case; otherwise tool limitation, no agent rewrite of legal source","rewrite_or_none","substitute accepted syntax unsupported by Slither"),
("other",None,"unmatched compiler diagnostic","Observed diagnostic has no verified template yet.","unclassified: enumerate every normalized template, establish cause before routing","undetermined","not defined until cause is established"),
("json_error","JSONError","Invalid JSON input|Unknown key|Invalid component","Malformed standard-JSON input; diagnostic probes only, not main compilation path.","deterministic repair of caller input, not Solidity source","none",None),
("io_error","IOError","File not found|Permission denied|File outside of allowed directories","The compiler cannot read a requested source.","deterministic path/permission configuration within approved scope; no dependency download","none","modify an import path"),
("docstring_error","DocstringParsingError","Documentation tag|Documented parameter|@return","NatSpec tags refer to absent or inconsistent declarations.","deterministic exact tag-name correction if binding is unique; otherwise agent","rewrite","alter a NatSpec parameter name"),
("syntax_error","SyntaxError","outside of a for|not inside a loop|No visibility specified","Parsed construct violates a syntactic context restriction.","deterministic documented context correction only if behavior is preserved; otherwise agent","rewrite","move continue outside its loop"),
("unimplemented_feature","UnimplementedFeatureError","Unimplemented feature|not yet supported|not implemented","Compiler feature is not implemented for this version or code-generation mode.","deterministic existing candidate/settings selection; otherwise tool limitation","none","use a valid feature unavailable in the selected compiler"),
("internal_compiler_error","InternalCompilerError","Internal compiler error|InternalCompilerError","Compiler implementation failed internally; source location may be absent.","tool limitation: retain compiler/version/diagnostic and try only existing permitted candidates","none",None),
("compiler_exception","Exception","Exception|std::exception::what","Compiler exception with no stable more-specific diagnosis.","tool limitation; never infer a source repair from exception text alone","none",None),
("fatal_error","FatalError","Fatal error|FatalError","Unhandled fatal compiler condition.","tool limitation; preserve crash evidence, no arbitrary source rewrite","none",None),
("warning","Warning","Warning: <message>","Non-fatal diagnostic; not a failed compilation.","no repair required","none",None),
("unsupported_disjunction",None,"F: unsupported pragma expression; expression contains ||","Frozen interval semantics do not represent a union.","later deterministic union of intervals with ordered attempts; CP3 classification only","none","replace a supported interval with a disjunction"),
("unsupported_expression",None,"F: unsupported pragma expression","Malformed or unsupported version expression without a proven missing terminator.","agent when source malformed; tool limitation when legal expression unsupported","rewrite_or_none","modify a version token"),
("unterminated_pragma",None,"F: unterminated pragma directive","A top-level Solidity pragma has no terminator before braces or EOF.","deterministic insertion only if unique; otherwise agent","additive","delete a pragma semicolon"),
("pragma_missing_semicolon_candidate",None,"F: unsupported pragma expression; expression includes directive keyword","The expression consumes a following import/pragma/contract/interface/library/abstract token.","deterministic unique semicolon insertion only after compiler validation; keep original expression evidence","additive","delete a pragma semicolon before another directive"),
("slither_no_timeout",None,"no completed API call","In-process Slither has no enforced timeout; absence of timeout records is not evidence of no hangs.","later subprocess isolation and explicit deadline; no implementation in CP3","none",None)
]
sources={
 "error_types":{"tag":"v0.7.6","path":"docs/using-the-compiler.rst","section":"Error types"},
 "imports":{"tag":"v0.8.38","path":"docs/path-resolution.rst","section":"Import Path Resolution; Import Remapping"},
 "layout":{"tag":"v0.8.38","path":"docs/layout-of-source-files.rst","section":"SPDX License Identifier; Pragmas; Importing other Source Files"},
 "old_imports":{"tag":"v0.4.12","path":"docs/layout-of-source-files.rst","section":"Importing other Source Files"},
 "cp3":{"path":"compile_repair/PROMPTS.md","section":"4.5; D3; D6; D7"}
}
rows=[]
for key,types,template,cause,repair,level,operator in definitions:
 refs=["error_types","cp3"]
 if key in ("unresolved_package_import","missing_relative_file","io_error"):refs+=["imports","old_imports"]
 elif key in ("multiple_license_or_pragma","closure_version_conflict") or "pragma" in key or key.startswith("unsupported"):refs+=["layout"]
 rows.append(dict(category=key,solc_error_types=types.split(",") if types else [],message_templates=[template],error_codes=[],cause=cause,sources=refs,candidate_repair=repair,change_level=level,verification=["D3: solc rc0, Slither construction, all input mappings, complete ContractDefinition coverage","D7: exact old-byte precondition, preserve source, per-file edit level, diagnostic-line restriction for rewrites, byte provenance and node marking"],verified_versions=[],cp4_operator=operator))
# Short independent summaries, keyed by the first line of every change bullet.
change_text={
"v0.5.0":"""
24|Signed right shifts round toward negative infinity|runtime
29|Continue in do-while jumps to the condition|runtime
33|Low-level calls no longer pad a bytes argument|runtime
36|View and pure external calls use STATICCALL on suitable EVMs|runtime
40|ABI encoding pads calldata bytes and strings correctly|runtime
45|ABI decoding checks bounds and padding before executing|runtime
49|External calls forward available gas on suitable EVMs|runtime
57|Low-level calls and hashing require one bytes argument|type_error_other
69|Low-level calls return success and return-data tuple|type_error_other
74|Local variables follow C99 declaration scope|undeclared_identifier
86|Functions require explicit visibility|syntax_error
90|Reference-typed variables require explicit data location|type_error_other
98|Contract members no longer include address operations|type_error_other
105|Unrelated contract casts are disallowed|type_error_other
113|Payable and nonpayable address types are distinct|type_error_other
124|Fixed bytes and integer casts require equal widths or intermediate casts|type_error_other
132|Reading msg.value requires a payable public entry context|type_error_other
137|Reading CLI standard input requires the dash target|interface
150|The obsolete formal CLI mode is removed|interface
155|The Julia CLI mode is renamed Yul|interface
158|Clone bytecode output options are removed|interface
161|Import remapping cannot have an empty prefix|io_error
163|AST mutability replaces legacy constant and payable fields|interface
166|AST function kind replaces the constructor boolean|interface
170|Link placeholders use a hash of the qualified library name|interface
181|Constructor declarations require the constructor keyword|syntax_error
183|Base-constructor invocation requires parentheses|syntax_error
185|Repeated base-constructor argument specifications are rejected|duplicate_definition
188|Wrong constructor argument counts are rejected|type_error_other
195|callcode is removed; migration can change call semantics|type_error_other
198|suicide spelling is removed|undeclared_identifier
200|sha3 spelling is removed|undeclared_identifier
202|throw is removed|syntax_error
208|Decimal-to-fixed-bytes literal casts require explicit intermediate types|type_error_other
211|Hex-literal to fixed-bytes conversions require matching widths|type_error_other
217|The years denomination is removed|parser_error_other
220|Numeric trailing dots require a following digit|parser_error_other
222|Hex numbers cannot be combined with unit denominations|type_error_other
225|Hex numeric prefixes must use lowercase x|parser_error_other
230|Empty struct declarations are rejected|syntax_error
232|Inferred var declarations are removed|syntax_error
234|Tuple assignments require equal component counts|type_error_other
237|Constants require compile-time constant expressions|type_error_other
239|Multi-variable declarations require matching value counts|type_error_other
242|Uninitialized storage references are rejected|type_error_other
244|Empty tuple expressions are rejected|type_error_other
246|Dependency-cycle analysis has a depth limit|type_error_other
249|Fixed arrays cannot have zero length|type_error_other
254|The constant function-mutability spelling is removed|parser_error_other
256|Booleans cannot use arithmetic operators|type_error_other
258|Unary plus is removed|syntax_error
260|Packed ABI encoding requires typed literal arguments|type_error_other
263|Functions returning values cannot use a bare return|type_error_other
266|Loose assembly jumps and stack-only instructions are removed|parser_error_other
270|Unimplemented functions cannot carry modifiers|syntax_error
272|Function types cannot name their return values|syntax_error
274|Unbraced control-flow bodies cannot be variable declarations|syntax_error
277|Calldata and constructor become keywords|parser_error_other
279|Additional reserved words cannot be identifiers|parser_error_other
""",
"v0.6.0":"""
18|Exponentiation results use the base type|runtime
30|Overriding requires virtual and override with explicit competing bases|type_error_other
38|Array length is readonly and mutation requires push or pop|type_error_other
44|Incomplete contracts require abstract|type_error_other
47|Libraries must implement all declared functions|type_error_other
49|Assembly identifiers cannot end with storage suffixes|declaration_error
51|Assembly declarations cannot shadow outer declarations|duplicate_definition
55|State-variable shadowing across inheritance is rejected|duplicate_definition
66|External function addresses require the address member|type_error_other
69|Array push with a value no longer returns its length|type_error_other
71|Fallback declarations split into fallback and receive|parser_error_other
75|Receive handles empty calldata and is implicitly payable|runtime
78|Fallback handles unmatched calls and rejects value unless payable|runtime
91|Try-catch is newly available for failed external calls|feature
92|Struct and enum declarations may be at file scope|feature
93|Calldata arrays support slices|feature
95|NatSpec return names receive declaration checks|docstring_error
96|Yul leave exits a function|feature
97|The payable conversion accepts address values|feature
111|The new error reporter becomes the default|interface
117|Metadata uses IPFS by default with configurable hash mode|interface
132|The Yul optimizer is enabled with the general optimizer|interface
139|The C API transfers allocation and release responsibility to callers|interface
""",
"v0.7.0":"""
15|Literal exponentiation and shifts use uint256 or int256|runtime
25|Call gas and value options use braces|parser_error_other
29|The now alias is deprecated in favor of block.timestamp|undeclared_identifier
34|Variable NatSpec is restricted to public state variables|docstring_error
37|Gwei becomes a keyword|parser_error_other
40|Ordinary string literals require printable ASCII|encoding
43|Unicode-prefixed strings allow UTF-8 text|feature
46|Overrides may restrict state mutability|feature
57|Assembly user identifiers cannot contain dots|declaration_error
60|Assembly storage metadata uses dot-slot and dot-offset syntax|undeclared_identifier
69|Mapping-containing structs and arrays must stay in storage|type_error_other
73|Storage copies of mapping-containing aggregate values are rejected|type_error_other
81|Constructor visibility no longer controls abstractness|warning
85|Library functions cannot be virtual|type_error_other
88|Duplicate events in one inheritance hierarchy are rejected|duplicate_definition
91|Using directives are no longer inherited|type_error_other
98|Shift counts cannot be signed|type_error_other
101|Finney and szabo denominations are removed|parser_error_other
108|Var is now rejected during parsing|parser_error_other
115|Hex strings have a distinct AST literal kind|interface
116|Null AST members are omitted|interface
117|Constructor and function user documentation are consistent|interface
""",
"v0.8.0":"""
16|Arithmetic overflow and underflow revert unless unchecked|runtime
22|ABI coder v2 becomes the default|runtime
33|Exponentiation associates to the right|runtime
38|Assertion and internal failures return panic data via REVERT|runtime
46|Invalid storage-byte-array encoding causes a panic|runtime
49|Typed constants round in array-length expressions|runtime
53|The byte type alias is removed|undeclared_identifier
60|Literal casts enforce address width, integer bounds and enum range|type_error_other
74|Address literals are nonpayable unless explicitly converted|type_error_other
78|One explicit cast can change at most one type category|type_error_other
105|Call options must occur in a single brace block|type_error_other
107|High-level log0 through log4 functions are removed|undeclared_identifier
111|Enums cannot contain more than 256 values|type_error_other
115|Special names are forbidden for most declarations|declaration_error
119|Backspace, form-feed and vertical-tab escapes are removed|encoding
122|Sender and origin are nonpayable address values|type_error_other
129|Address conversions normally produce nonpayable addresses|type_error_other
147|The assembly chainid builtin requires view instead of pure|type_error_other
152|Combined-JSON ABI and documentation values become JSON objects|interface
155|Legacy AST output is removed|interface
158|The old error reporter is removed|interface
"""
}
# DeclarationError is an error-type family in addition to its concrete causes.
row=dict(rows[2]);row.update(category="declaration_error",message_templates=["Identifier <name> invalid or unavailable"],cause="A declaration violates a documented naming or binding rule.",cp4_operator="rename a declaration to a forbidden identifier");rows.append(row)
changes=[]
coverage={}
for tag,text in change_text.items():
 filename={"v0.5.0":"050","v0.6.0":"060","v0.7.0":"070","v0.8.0":"080"}[tag]+"-breaking-changes.rst"
 path=DOCS/("solidity-docs@"+tag)/"docs"/filename
 lines=path.read_text().splitlines()
 seen=[]
 for value in text.strip().splitlines():
  number,summary,category=value.split("|");number=int(number);seen.append(number)
  if category in ("runtime","interface","feature"):
   types=[];templates=[];repair="no source repair solely for this change; select a compatible compiler/tool interface; runtime semantics require separate assessment"
   level="none";operator=None
  else:
   base=next(r for r in rows if r["category"]==category);types=base["solc_error_types"];templates=base["message_templates"];repair=base["candidate_repair"];level=base["change_level"];operator=base["cp4_operator"]
  changes.append(dict(id=tag+"-L"+str(number),category=category,summary=summary,cause=summary,
   solc_error_types=types,message_templates=templates,error_codes=[],verified_versions=[],
   documentation={"tag":tag,"path":"docs/"+filename,"line":number},
   candidate_repair=repair,change_level=level,verification=["D3(a/b)","D7 byte and diagnostic-line checks"],
   cp4_operator=operator,compile_failure_class=category not in ("runtime","interface","feature","warning")))
 # Upgrade examples repeat these changes and are not independent omissions.
 stop=next(i+1 for i,l in enumerate(lines) if l in ("How to update your code","Interoperability With Older Contracts"))
 bullets=[i+1 for i,l in enumerate(lines[:stop-1]) if re.match(r"^\s*\* ",l)]
 missing=sorted(set(bullets)-set(seen))
 if missing:raise ValueError((tag,missing))
 coverage[tag]={"all_change_bullet_lines":bullets,"covered_bullet_lines":sorted(set(bullets)&set(seen)),"extra_prose_change_lines":sorted(set(seen)-set(bullets)),"upgrade_section_is_cross_reference":True}
manifest=json.loads((BASE/"document_manifest.json").read_text())
result={"schema":"cp3-taxonomy-v1","author":"Codex","basis":"PROMPTS r2.13 section 4.5; established before corpus-content statistics","corpus_independent":True,
 "sources":sources,"document_manifest_sha256":hashlib.sha256((BASE/"document_manifest.json").read_bytes()).hexdigest(),
 "diagnostic_policy":{"primary":"combined-json CLI stderr","standard_json":"type/errorCode diagnostic probes only, never the compilation route","error_code_optional":True,"verified_versions":"populated only from recorded probes; document introduction versions do not imply empirically tested ranges","warning_is_failure":False},
 "categories":rows,"breaking_changes":changes,"breaking_change_coverage":coverage,
 "retention_policy":"Keep all documented categories even with zero observed cases; append evidence rather than remove classes."}
target=BASE/"taxonomy.json"
with target.open("x",encoding="utf8") as f:json.dump(result,f,ensure_ascii=False,indent=2);f.write("\n")
seal={"taxonomy_sha256":hashlib.sha256(target.read_bytes()).hexdigest(),"categories":len(rows),"breaking_change_items":len(changes),"corpus_content_statistics_started":False}
with (BASE/"taxonomy_initial_receipt.json").open("x") as f:json.dump(seal,f,indent=2);f.write("\n")
print(json.dumps(seal))
