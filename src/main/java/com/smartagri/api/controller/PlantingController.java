package com.smartagri.api.controller;

import com.smartagri.api.entity.Planting;
import io.swagger.v3.oas.annotations.Operation;
import io.swagger.v3.oas.annotations.Parameter;
import io.swagger.v3.oas.annotations.tags.Tag;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import javax.validation.Valid;
import java.util.ArrayList;
import java.util.List;

/**
 * 种植管理Controller
 */
@RestController
@RequestMapping("/api/v1/planting")
@Tag(name = "种植管理", description = "种植信息的增删改查接口")
public class PlantingController {

    /**
     * 创建种植
     */
    @PostMapping
    @Operation(summary = "创建种植")
    public ResponseEntity<Planting> createPlanting(@Valid @RequestBody Planting planting) {
        // TODO: 实现创建种植的业务逻辑
        return ResponseEntity.ok(planting);
    }

    /**
     * 修改种植
     */
    @PutMapping("/{plantingId}")
    @Operation(summary = "修改种植")
    public ResponseEntity<Planting> updatePlanting(
            @PathVariable Long plantingId,
            @Valid @RequestBody Planting planting) {
        // TODO: 实现修改种植的业务逻辑
        return ResponseEntity.ok(planting);
    }

    /**
     * 删除种植
     */
    @DeleteMapping("/{plantingId}")
    @Operation(summary = "删除种植")
    public ResponseEntity<Void> deletePlanting(@PathVariable Long plantingId) {
        // TODO: 实现删除种植的业务逻辑
        return ResponseEntity.ok().build();
    }

    /**
     * 获取种植
     */
    @GetMapping("/{plantingId}")
    @Operation(summary = "获取种植")
    public ResponseEntity<Planting> getPlanting(@PathVariable Long plantingId) {
        // TODO: 实现获取种植的业务逻辑
        return ResponseEntity.ok(new Planting());
    }

    /**
     * 获取地块下的种植列表
     */
    @GetMapping("/list")
    @Operation(summary = "获取地块下的种植列表")
    public ResponseEntity<List<Planting>> getPlantingList(
            @Parameter(description = "地块ID") @RequestParam Long landBlockId,
            @Parameter(description = "种植状态") @RequestParam(required = false) Integer status) {
        // TODO: 实现获取地块下种植列表的业务逻辑
        return ResponseEntity.ok(new ArrayList<>());
    }
} 