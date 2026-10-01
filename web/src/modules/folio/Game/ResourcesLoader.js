import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js'
import { DRACOLoader } from 'three/addons/loaders/DRACOLoader.js'
import { KTX2Loader } from 'three/addons/loaders/KTX2Loader.js'
import * as THREE from 'three/webgpu'
import { Game } from './Game.js'
import { FOLIO_ASSET_BASE, folioAsset } from '../assetBase.js'

export class ResourcesLoader
{
    constructor()
    {
        this.game = Game.getInstance()
        this.loaders = new Map()
        this.cache = new Map()
    }

    getLoader(_type)
    {
        if(this.loaders.has(_type))
            return this.loaders.get(_type)

        let loader = null
        
        if(_type === 'texture')
        {
            loader = new THREE.TextureLoader()
        }
        else if(_type === 'textureKtx')
        {
            loader = new KTX2Loader()
            loader.setTranscoderPath(`${FOLIO_ASSET_BASE}basis/`)
            loader.detectSupport(this.game.rendering.renderer)
        }
        else if(_type === 'draco')
        {
            loader = new DRACOLoader()
            loader.setDecoderPath(`${FOLIO_ASSET_BASE}draco/`)
            loader.preload()
        }
        else if(_type === 'gltf')
        {
            const dracoLoader = this.getLoader('draco')

            const ktx2Loader = this.getLoader('textureKtx')
            
            loader = new GLTFLoader()
            loader.setDRACOLoader(dracoLoader)
            loader.setKTX2Loader(ktx2Loader)
        }

        if(loader && typeof loader.load === 'function')
        {
            const originalLoad = loader.load.bind(loader)
            loader.load = (url, onLoad, onProgress, onError) =>
                originalLoad(folioAsset(url), onLoad, onProgress, onError)
        }

        this.loaders.set(_type, loader)

        return loader
    }

    load(_files, _progressCallback = null)
    {
        return new Promise((resolve, reject) =>
        {
            let toLoad = _files.length
            const loadedResources = {}

            // Progress
            const progress = () =>
            {
                toLoad--

                if(typeof _progressCallback === 'function')
                    _progressCallback(toLoad, _files.length)
                
                if(toLoad === 0)
                    resolve(loadedResources)
            }

            // Save
            const save = (_file, _resource) =>
            {
                // Apply modifier
                if(typeof _file[3] !== 'undefined')
                    _file[3](_resource)
                    
                // Save in resources object
                loadedResources[_file[0]] = _resource

                // Save in cache
                this.cache.set(_file[1], _resource)
            }

            // Error
            const error = (_file) =>
            {
                console.log(`Resources > Couldn't load file ${_file[1]}`)
                reject(_file[1])
            }

            // Each file
            for(const _file of _files)
            {
                const resolvedPath = folioAsset(_file[1])
                const cacheKey = resolvedPath

                // In cache
                if(this.cache.has(cacheKey) || this.cache.has(_file[1]))
                {
                    // Save cached file directly in resources object
                    loadedResources[_file[0]] = this.cache.get(cacheKey) || this.cache.get(_file[1])

                    progress()
                }

                // Not in cache
                else
                {
                    const loader = this.getLoader(_file[2])
                    loader.load(
                        resolvedPath,
                        resource => {
                            save([_file[0], cacheKey, _file[2], _file[3]], resource)
                            progress()
                        },
                        undefined,
                        () => error(_file)
                    )
                }
            }
        })
    }
}
