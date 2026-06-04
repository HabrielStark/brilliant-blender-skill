#!/usr/bin/env node
export interface GlbReport {
    ok: boolean;
    path: string;
    sizeBytes: number;
    sizeMb: number;
    nodes: number;
    meshes: number;
    materials: number;
    animations: number;
    animationNames: string[];
    cameras: number;
    textures: number;
    externalTextures: string[];
    generator: string | null;
    errors: string[];
    warnings: string[];
}
export declare function validateGlb(path: string, opts?: {
    maxMb?: number;
    requireAnimation?: boolean;
}): Promise<GlbReport>;
