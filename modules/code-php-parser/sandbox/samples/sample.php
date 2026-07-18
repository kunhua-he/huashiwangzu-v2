<?php
/**
 * 示例 PHP 文件
 * 用于切块测试
 */

// 工具函数
function hello($name) {
    return "hello " . $name;
}

class Greeter {
    public function greet() {
        return hello("world");
    }
}
