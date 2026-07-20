package com.smartagri.api.controller;

import com.smartagri.api.entity.Base;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;

/**
 * 基地管理Controller
 */
@RestController
@RequestMapping("/api/v1/lands/bases")
@Tag(name = "基地管理", description = "基地信息的增删改查接口")
public class BaseController {

    /**
     * 创建基地
     */
    @PostMapping
    @Operation(summary = "创建基地")
    public ResponseEntity<Base> createBase(@Valid @RequestBody Base base) {
        // TODO: 实现创建基地的业务逻辑
        return ResponseEntity.ok(base);
    }

    /**
     * 搜索基地摘要信息分页
     */
    @GetMapping
    @Operation(summary = "搜索基地摘要信息分页")
    public ResponseEntity<Page<Base>> searchBases(
            @Parameter(description = "基地名称") @RequestParam(required = false) String name,
            @Parameter(description = "地址关键字") @RequestParam(required = false) String address,
            Pageable pageable) {
        // TODO: 实现搜索基地的业务逻辑
        return ResponseEntity.ok(Page.empty());
    }

    /**
     * 获得基地详情
     */
    @GetMapping("/{id}")
    @Operation(summary = "获得基地详情")
    public ResponseEntity<Base> getBase(@PathVariable Long id) {
        // TODO: 实现获取基地详情的业务逻辑
        return ResponseEntity.ok(new Base());
    }

    /**
     * 更新基地信息
     */
    @PutMapping("/{id}")
    @Operation(summary = "更新基地信息")
    public ResponseEntity<Base> updateBase(@PathVariable Long id, @Valid @RequestBody Base base) {
        // TODO: 实现更新基地的业务逻辑
        return ResponseEntity.ok(base);
    }

    /**
     * 删除基地
     */
    @DeleteMapping("/{id}")
    @Operation(summary = "删除基地")
    public ResponseEntity<Void> deleteBase(@PathVariable Long id) {
        // TODO: 实现删除基地的业务逻辑
        return ResponseEntity.ok().build();
    }

    /**
     * 更新基地经纬度信息
     */
    @PutMapping("/{id}/location")
    @Operation(summary = "更新基地经纬度信息")
    public ResponseEntity<Base> updateBaseLocation(
            @PathVariable Long id,
            @Parameter(description = "经度") @RequestParam Double longitude,
            @Parameter(description = "纬度") @RequestParam Double latitude) {
        // TODO: 实现更新基地经纬度的业务逻辑
        return ResponseEntity.ok(new Base());
    }
} 