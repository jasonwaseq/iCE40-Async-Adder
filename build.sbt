// iCE40 Async Adder - Chisel 3 + Scala FIRRTL (no CIRCT/firtool; works on Windows)
ThisBuild / scalaVersion := "2.12.18"
ThisBuild / version := "0.1.0"
ThisBuild / organization := "ice40.async"

val chiselVersion = "3.6.1"

lazy val root = (project in file("."))
  .settings(
    name := "ice40-async-adder",
    Compile / run / mainClass := Some("add.ADD"),
    libraryDependencies ++= Seq(
      "edu.berkeley.cs" %% "chisel3" % chiselVersion,
      "org.scalatest" %% "scalatest" % "3.2.17" % "test",
    ),
    scalacOptions ++= Seq(
      "-language:reflectiveCalls",
      "-deprecation",
      "-feature",
      "-Xcheckinit",
    ),
    addCompilerPlugin("edu.berkeley.cs" % "chisel3-plugin" % chiselVersion cross CrossVersion.full),
  )
