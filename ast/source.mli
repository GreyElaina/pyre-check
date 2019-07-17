(* Copyright (c) 2016-present, Facebook, Inc.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree. *)

type mode =
  | Default
  | DefaultButDontCheck of int list
  | Declare
  | Strict
  | Infer
  | PlaceholderStub
[@@deriving compare, eq, show, sexp, hash]

module Metadata : sig
  type t = {
    autogenerated: bool;
    debug: bool;
    local_mode: mode;
    ignore_lines: Ignore.t list;
    number_of_lines: int;
    version: int
  }
  [@@deriving compare, eq, show, hash, sexp]

  val create
    :  ?autogenerated:bool ->
    ?debug:bool ->
    ?declare:bool ->
    ?ignore_lines:Ignore.t list ->
    ?strict:bool ->
    ?version:int ->
    number_of_lines:int ->
    unit ->
    t

  val parse : qualifier:Reference.t -> string list -> t
end

type t = {
  docstring: string option;
  hash: int;
  metadata: Metadata.t;
  handle: File.Handle.t;
  qualifier: Reference.t;
  statements: Statement.t list
}
[@@deriving compare, eq, hash, show, sexp]

val mode : configuration:Configuration.Analysis.t -> local_mode:mode option -> mode

val create
  :  ?docstring:string option ->
  ?metadata:Metadata.t ->
  ?handle:File.Handle.t ->
  ?qualifier:Reference.t ->
  ?hash:int ->
  Statement.t list ->
  t

val hash : t -> int

val signature_hash : t -> int

val ignore_lines : t -> Ignore.t list

val statements : t -> Statement.t list

val qualifier : handle:File.Handle.t -> Reference.t

val top_level_define : t -> Statement.Define.t

val top_level_define_node : t -> Statement.Define.t Node.t

val expand_relative_import : from:Reference.t -> t -> Reference.t
