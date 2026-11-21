import * as multilineArrays from "prettier-plugin-multiline-arrays";
import * as maafwSort from "@nekosu/prettier-plugin-maafw-sort";

// 排序范围：只对 MPE 导出的 pipeline/*.json 生效。
// interface.json 必须同时关掉 pattern 与 detect，否则会被内容探测命中并排序。
export default {
    plugins: [maafwSort.patchPlugin(multilineArrays)],
    multilineArraysWrapThreshold: 1,
    tabWidth: 4,
    printWidth: 120,
    useTabs: false,
    bracketSameLine: true,
    bracketSpacing: false,
    endOfLine: "auto",
    maafwPipelinePatterns: ["/pipeline/.*\\.jsonc?"],
    maafwInterfacePatterns: [],
    maafwInterfaceDetect: false,
    maafwLocalePatterns: [],
    overrides: [
        {
            files: ["**/*.yml", "**/*.yaml"],
            options: {
                parser: "yaml",
                tabWidth: 2
            }
        },
        {
            files: ["*.json"],
            options: {
                parser: "json",
                useTabs: false,
                bracketSameLine: false
            }
        }
    ]
};
