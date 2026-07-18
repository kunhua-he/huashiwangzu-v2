/**
 * 示例 JS/TS 模块
 */

// 工具函数
export function hello(name) {
  return `hello ${name}`;
}

export class Greeter {
  greet() {
    return hello("world");
  }
}

const answer = 42;
