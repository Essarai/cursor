package com.smartagri.api.controller;

import com.smartagri.api.entity.LandBlock;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;

/**
 * 地块管理Controller
 */
@RestController
@RequestMapping("/api/v1/lands/land-blocks")
@Tag(name = "地块管理", description = "地块信息的增删改查接口")
public class LandBlockController {

    /**
     * 创建地块
     */
    @PostMapping
    @Operation(summary = "创建地块")
    public ResponseEntity<LandBlock> createLandBlock(@Valid @RequestBody LandBlock landBlock) {
        // TODO: 实现创建地块的业务逻辑
        return ResponseEntity.ok(landBlock);
    }

    /**
     * 搜索地块摘要信息分页
     */
    @GetMapping
    @Operation(summary = "搜索地块摘要信息分页")
    public ResponseEntity<Page<LandBlock>> searchLandBlocks(
            @Parameter(description = "所属基地ID") @RequestParam(required = false) Long baseId,
            @Parameter(description = "地块名称") @RequestParam(required = false) String name,
            @Parameter(description = "地块类型") @RequestParam(required = false) Integer type,
            Pageable pageable) {
        // TODO: 实现搜索地块的业务逻辑
        return ResponseEntity.ok(Page.empty());
    }

    /**
     * 获得地块详情
     */
    @GetMapping("/{id}")
    @Operation(summary = "获得地块详情")
    public ResponseEntity<LandBlock> getLandBlock(@PathVariable Long id) {
        // TODO: 实现获取地块详情的业务逻辑
        return ResponseEntity.ok(new LandBlock());
    }

    /**
     * 更新地块信息
     */
    @PutMapping("/{id}")
    @Operation(summary = "更新地块信息")
    public ResponseEntity<LandBlock> updateLandBlock(@PathVariable Long id, @Valid @RequestBody LandBlock landBlock) {
        // TODO: 实现更新地块的业务逻辑
        return ResponseEntity.ok(landBlock);
    }

    /**
     * 删除地块
     */
    @DeleteMapping("/{id}")
    @Operation(summary = "删除地块")
    public ResponseEntity<Void> deleteLandBlock(@PathVariable Long id) {
        // TODO: 实现删除地块的业务逻辑
        return ResponseEntity.ok().build();
    }

    /**
     * 更新地块经纬度信息
     */
    @PutMapping("/{id}/location")
    @Operation(summary = "更新地块经纬度信息")
    public ResponseEntity<LandBlock> updateLandBlockLocation(
            @PathVariable Long id,
            @Parameter(description = "经度") @RequestParam Double longitude,
            @Parameter(description = "纬度") @RequestParam Double latitude) {
        // TODO: 实现更新地块经纬度的业务逻辑
        return ResponseEntity.ok(new LandBlock());
    }
} 