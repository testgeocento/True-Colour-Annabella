""" the osgeo package contains the GDAL, OGR and OSR libraries """

""" for python 2 and python 3 execution exec(open("./path/to/script.py").read(), globals()) """

import sys, os, json

from osgeo import gdal, osr, ogr

sys.path.append('/usr/bin/')
import gdal_merge
import gdal_pansharpen
import time

import generic

def Usage():
    print('Usage: trueColour(args)')

def trueColour(argv):
    
    
    inputDirectory = sys.argv[1]
    outputDirectory = sys.argv[2]
    platformName = sys.argv[3]
    productType = sys.argv[4]
    if len(sys.argv) == 6:
        aoiwkt = sys.argv[5]
    else:   
        aoiwkt = None

    print gdal.VersionInfo()

    gdal.UseExceptions()

    if platformName == 'PLEIADES' or platformName == 'SPOT':
        
        start = time.time()
        #Look for JPEG2000 files and then look for TIFF files
        jp2FilePaths = findFiles(inputDirectory, "jp2")
        tiffFilePaths = findFiles(inputDirectory, ("tiff", "tif"))
        #Create another array containing the filepaths regardless of file type
        if len(jp2FilePaths) > 0:
            imageFilePaths = jp2FilePaths
        elif len(tiffFilePaths) > 0:
            imageFilePaths = tiffFilePaths #Transfer all filepaths to imageFilePaths array no matter what type of file they are
        else: #It couldn't find jp2 or tiff files
            sys.exit("Missing image files in directory " + inputDirectory)
    
        panTileFilePaths = []
        msTileFilePaths = []
        ps4bandTileFilePaths = []
        psRGBTileFilePaths = []
        psRGNTileFilePaths = []
    
        #Label the files
        for filePath in imageFilePaths:
            path, fileName = os.path.split(filePath) #Splits filepaths in imageFilePaths array into path and filename
            if "_P_" in fileName:
                print ("Image is panchromatic.")
                panTileFilePaths.append(filePath)
            elif "_MS_" in fileName:
                print ("Image is 4 bands multispectral.")
                msTileFilePaths.append(filePath)
            elif "_PMS_" in fileName:
                print ("Image is 4 bands pansharpened.")
                ps4bandTileFilePaths.append(filePath)
            elif "_PMS-N_" in fileName:
                print ("Image is 3 bands pansharpened (B, G, R bands).")
                psRGBTileFilePaths.append(filePath)
            elif "_PMS-X_" in fileName:
                print ("Image is 3 bands pansharpened (G, R, NIR bands, false colour).")
                psRGNTileFilePaths.append(filePath)
    
        # Check if images are tiled.
        panImageFilePath = mosaic(panTileFilePaths, "/panmosaic.vrt", outputDirectory)
        msImageFilePath = mosaic(msTileFilePaths, "/msmosaic.vrt", outputDirectory)
        ps4bandImageFilePath = mosaic(ps4bandTileFilePaths, "/ps4bandmosaic.vrt", outputDirectory)
        psRGBImageFilePath = mosaic(psRGBTileFilePaths, "/psRGBmosaic.vrt", outputDirectory)
        psRGNImageFilePath = mosaic(psRGNTileFilePaths, "/psRGNmosaic.vrt", outputDirectory)
    
        finalImageFilePath = None
        if panImageFilePath and msImageFilePath: #If they both exist then it's a bundle.
            finalImageFilePath = outputDirectory + "/pansharpen.vrt"
            gdal_pansharpen.gdal_pansharpen(['', panImageFilePath, msImageFilePath, finalImageFilePath, '-nodata', '0', '-co', 'PHOTOMETRIC=RGB', '-of', 'VRT'])
        elif panImageFilePath: #It's just a pan file
            finalImageFilePath = panImageFilePath
        elif msImageFilePath: #It's just an MS file
            finalImageFilePath = msImageFilePath
        elif ps4bandImageFilePath:
            finalImageFilePath = ps4bandImageFilePath
        elif psRGBImageFilePath:
            finalImageFilePath = psRGBImageFilePath
        elif psRGNImageFilePath:
            finalImageFilePath = psRGNImageFilePath
    
        output(finalImageFilePath, outputDirectory, aoiwkt, start)
        
        print ("True Colour script finished for PLEIADES product(s) at " + inputDirectory)
        executionTime = time.time() - start
        print(executionTime)
       
    elif platformName == 'KOMPSAT-2':
        
        start = time.time()
        #Find tiff files
        tiffFilesPaths = findFiles(inputDirectory, ("tif", "tiff"))

        if len(tiffFilesPaths) == 0:
            sys.exit("No TIFF file in the directory " + inputDirectory)
    
        elif len(tiffFilesPaths) == 1:  #KOMPSAT 2 pansharpened
            print ("Found 1 tiff file.")
            PStiffFilePath = tiffFilesPaths[0]
            path, fileName = os.path.split(PStiffFilePath)
            if "_1G_1MC.TIF" or "_PS.TIF" in fileName.upper():
                #Convert to vrt
                panSharpenFilePath = outputDirectory + "/pansharpen.vrt"
                gdal.Translate(panSharpenFilePath, PStiffFilePath, format = "VRT")
            else:
                sys.exit("Unable to identify file type.")
            
        #Bundle = 1 pan file, 4 MS files - make composite MS image then pansharpen
        elif len(tiffFilesPaths) == 5:
            print ("Found 5 tiff files.")
            #Label the pan and MS files
            bandFilePaths = []
            panFilePathArray = []
    
            #Locate pan file
            for filePath in tiffFilesPaths:
                path, fileName = os.path.split(filePath)
                if "PN" in fileName.upper() and "_1" in fileName.upper():
                    panFilePathArray.append(filePath)
                elif "PP" in fileName.upper() and "_1" in fileName.upper():
                    panFilePathArray.append(filePath)

            #Check the correct number of pan files have been added to the array.
            if len(panFilePathArray) < 1:
                sys.exit("Unable to locate pan file in directory " + inputDirectory)
            elif len(panFilePathArray) > 1:
                sys.exit("More than one pan file found in directory" + inputDirectory)
            else:
                panFilePath = panFilePathArray[0]
    
            #Locate red files
            if not fileType(tiffFilesPaths, "R_1", None, bandFilePaths, 1):
                sys.exit("Error when locating red file.")
    
            #Locate green files
            if not fileType(tiffFilesPaths, "G_1R.TIF", "G_1G.TIF", bandFilePaths, 2):
                sys.exit("Error when locating green file.")
    
            #Locate blue files
            if not fileType(tiffFilesPaths, "B_1", None, bandFilePaths, 3):
                sys.exit("Error when locating blue file.")
    
            #Create composite MS image
            print ("Successfully located pan and MS files. Creating composite colour image.")
            #Create vrt for bands
            colourFilePath = outputDirectory + "/spectral.vrt"
            try:
                gdal.BuildVRT(colourFilePath, bandFilePaths, separate=True)
            except RuntimeError:
                sys.exit("Error with gdal.BuildVRT")
    
            #Now pansharpen
            panSharpenFilePath = outputDirectory + "/pansharpen.vrt"
            gdal_pansharpen.gdal_pansharpen(['', panFilePath, colourFilePath, panSharpenFilePath, '-nodata', '0', '-co', 'PHOTOMETRIC=RGB', '-of', 'VRT'])
    
        else:
            sys.exit("Invalid number of files found. " + str(len(tiffFilesPaths)) + " files found in directory " + inputDirectory)
    

        output(panSharpenFilePath, outputDirectory, aoiwkt, start)
    
        print ("True Colour script finished for Kompsat-2 product(s) at " + inputDirectory)
        totalExecutionTime = time.time()-start
        print ("Total execution time: " + str(totalExecutionTime))
    
    elif platformName == 'KOMPSAT-3':
        
        start = time.time()
        tiffFilesPath = findFiles(inputDirectory, ("tif", "tiff"))
    
        if len(tiffFilesPath) < 1:
            sys.exit("Missing image files in directory " + inputDirectory)
    
        pantileFilePaths = []
        redtileFilePaths = []
        greentileFilePaths = []
        bluetileFilePaths = []
        PRtileFilePaths = []
        PGtileFilePaths = []
        PBtileFilePaths = []
    
        #Label files
        for filePath in tiffFilesPath:
            path, fileName = os.path.split(filePath)
            if "_P_R" in fileName.upper() or "_P.TIF" in fileName.upper(): #This will cause an issue as it'll be picked up by PG
                print ("Image is panchromatic.")
                pantileFilePaths.append(filePath)
            elif "_R_R" in fileName.upper() or "_R.TIF" in fileName.upper():
                print ("Image is red MS file.")
                redtileFilePaths.append(filePath)
            elif "_G_R" in fileName.upper() or "_G.TIF" in fileName.upper():
                print ("Image is green MS file.")
                greentileFilePaths.append(filePath)
            elif "_B_R" in fileName.upper() or "_B.TIF" in fileName.upper():
                print ("Image is blue MS file.")
                bluetileFilePaths.append(filePath)
            elif "_PR_R" in fileName.upper() or "_PR.TIF" in fileName.upper():
                print ("Image is pansharpened red file.")
                PRtileFilePaths.append(filePath)
            elif "_PG_R" in fileName.upper() or "_PG.TIF" in fileName.upper():
                print ("Image is pansharpened green file.")
                PGtileFilePaths.append(filePath)
            elif "_PB_R" in fileName.upper() or "_PB.TIF" in fileName.upper():
                print ("Image is pansharpened blue file.")
                PBtileFilePaths.append(filePath)
    
        #Check for tiles
        panimageFilePath = mosaic(pantileFilePaths, "/panmosaic.vrt", outputDirectory)
        redFilePath = mosaic(redtileFilePaths, "/redmosaic.vrt", outputDirectory)
        greenFilePath = mosaic(greentileFilePaths, "/greenmosaic.vrt", outputDirectory)
        blueFilePath = mosaic(bluetileFilePaths, "/bluemosaic.vrt", outputDirectory)
        PRFilePath = mosaic(PRtileFilePaths, "/PRmosaic.vrt", outputDirectory)
        PGFilePath = mosaic(PGtileFilePaths, "/PGmosaic.vrt", outputDirectory)
        PBFilePath = mosaic(PBtileFilePaths, "/PBmosaic.vrt", outputDirectory)
    
        if redFilePath and greenFilePath and blueFilePath:
            PSFiles = [redFilePath, greenFilePath, blueFilePath]
            #Create composite image from 3 bands
            MSFilePath = outputDirectory + "/MS.vrt"
            gdal.BuildVRT(MSFilePath, PSFiles, separate = True)
    
            if panimageFilePath:
                #Now panSharpen
                finalimageFilePath = outputDirectory + "/pansharpen.vrt"
                gdal_pansharpen.gdal_pansharpen(['', panimageFilePath, MSFilePath, finalimageFilePath, '-nodata', '0', '-co', 'PHOTOMETRIC=RGB', '-of', 'VRT'])
    
            else:
                finalimageFilePath = MSFilePath
    
        elif PRFilePath and PGFilePath and PBFilePath:
            PSFiles = [PRFilePath, PGFilePath, PBFilePath]
            #Combine 3 bands
            finalimageFilePath = outputDirectory + "/pansharpen.vrt"
            gdal.BuildVRT(finalimageFilePath, PSFiles, separate = True)
        
        else:
            sys.exit("Missing image files in directory " + inputDirectory)
            
        output(finalimageFilePath, outputDirectory, None, start)
    
        print ("True Colour script finished for Kompsat-3 product(s) at " + inputDirectory)
        executiontime = time.time()-start
        print("Total execution time: " + str(executiontime))

    elif platformName == "KOMPSAT-3A":
        
        start = time.time()
        #Find tiff files
        tiffFilePaths = findFiles(inputDirectory, ("tif", "tiff"))
    
        if len(tiffFilePaths) == 0:
            sys.exit("No TIFF file in the directory " + inputDirectory)
    
        elif len(tiffFilePaths) == 4: #Pansharpened KOMPSAT 3A, combine RGB bands into composite image
            print ("Found 4 files")
            PSFiles = []
    
            #Add red files to the array
            if not fileType(tiffFilePaths, "_PR.TIF", None, PSFiles, 1):
                sys.exit("Error when locating red file.")
    
            #Add green files to the array
            if not fileType(tiffFilePaths, "_PG.TIF", None, PSFiles, 2):
                sys.exit("Error when locating green file.")
    
            #Add blue files to the array
            if not fileType(tiffFilePaths, "_PB.TIF", None, PSFiles, 3):
                sys.exit("Error when locating blue file.")
    
            #Create composite PS image from 3 bands
            panSharpenFilePath = outputDirectory + "/pansharpened.vrt"
            gdal.BuildVRT(panSharpenFilePath, PSFiles, separate = True)
    
        #For a bundle
        elif len(tiffFilePaths) == 5: #Bundle = 1 pan file, 4 MS files - make composite MS image then pansharpen
            print ("Found 5 files")
            #Label the pan and MS files
            bandFilePaths = []
            panFilePathArray = []
            #Locate pan files
            if not fileType(tiffFilePaths, "_P.TIF", None, panFilePathArray, 1):
                sys.exit("Error when locating pan file.")
            panFilePath = panFilePathArray[0]
    
            #Locate red files
            if not fileType(tiffFilePaths, "_R.TIF", None, bandFilePaths, 1):
                sys.exit("Error when locating red file.")
    
            #Locate green files
            if not fileType(tiffFilePaths, "_G.TIF", None, bandFilePaths, 2):
                sys.exit("Error when locating green file.")
    
            #Locate blue files
            if not fileType(tiffFilePaths, "_B.TIF", None, bandFilePaths, 3):
                sys.exit("Error when locating blue file.")
    
            #Create composite MS image
            #Create vrt for bands
            colourFilePath = outputDirectory + "/spectral.vrt"
            try:
                gdal.BuildVRT(colourFilePath, bandFilePaths, separate=True)
            except RuntimeError:
                print ("Error with gdal.BuildVRT")
    
            #Now pansharpen
            panSharpenFilePath = outputDirectory + "/pansharpen.vrt"
            gdal_pansharpen.gdal_pansharpen(['', panFilePath, colourFilePath, panSharpenFilePath, '-nodata', '0', '-co', 'PHOTOMETRIC=RGB', '-of', 'VRT'])
    
        else:
            sys.exit("Invalid number of files found. " + len(tiffFilePaths) + " files found in directory " + inputDirectory)
    
        output(panSharpenFilePath, outputDirectory, None, start)
    
        print ("True Colour script finished for Kompsat-3A product(s) at " + inputDirectory)
        executiontime = time.time()-start
        print("Total execution time: " + str(executiontime))
    
def findFiles(directory, extension):
    print("scanning directory " + directory + " for files with extension " + str(extension))
    foundFiles = []
    for dirpath, dirnames, files in os.walk(directory):
        for name in files:
            print("File " + name)
            if name.lower().endswith(extension):
                print "Adding file " + name + " at " + dirpath
                foundFiles.append(os.path.join(dirpath, name))
    return foundFiles

def fileType(filesPathArray, string, string2, outputArray, expectedLength):
    returnStatus = True
    for filePath in filesPathArray:
        path, fileName = os.path.split(filePath)
        if string and string2:
            if string in fileName.upper():
                outputArray.append(filePath)
            elif string2 in fileName.upper():
                outputArray.append(filePath)
        elif string:
            if string in fileName.upper():
                outputArray.append(filePath)
        else:
            print ("Missing string.")
    # Check the correct number of files have been added to the array.
    if len(outputArray) < expectedLength:
        returnStatus = False
        if string and string2:
            print ("Unable to locate file with " + string + " or " + string2 + " in filename.")
        elif string:
            print ("Unable to locate file with " + string + " in filename.")
    elif len(outputArray) > expectedLength:
        returnStatus = False
        if string and string2:
            print ("More than one file with " + string + " or " + string2 + " in filename.")
        elif string:
            print ("More than one file with " + string + " in filename.")
    return returnStatus
    
def mosaic(filePathsArray, fileName, outputDirectory):
    if len(filePathsArray) > 1: #If there is more than one pan file, mosaic the tiles.
        filePath = outputDirectory + fileName
        gdal.BuildVRT(filePath, filePathsArray)
        print ("Mosaic complete.")
    elif len(filePathsArray) == 1:
        filePath = outputDirectory + fileName
        #Convert to vrt format.
        gdal.Translate(filePath, filePathsArray[0], format = "VRT")
        print ("No mosaic necessary.")
    else:
        filePath = False
    return filePath

def output(imageFilePath, outputDirectory, aoiwkt, start):
    ds = gdal.Open(imageFilePath)

    #Reproject and extract footprint
    warpedFilePath = outputDirectory + "/warped.vrt"
    beforeWarp = time.time()-start
    ds = gdal.Warp(warpedFilePath, ds, format = 'VRT', dstSRS = 'EPSG:4326')
    afterWarp = time.time()-start
    warpTime = afterWarp-beforeWarp
    print ("Warp takes %f seconds" % (warpTime))

    productFootprintWKT = generic.getDatasetFootprint(ds)
    print ("Footprint: " + productFootprintWKT)

    scaleParams = generic.getScaleParams(ds, 255)
    print ("Scale params: " + str(scaleParams))

    #Convert to tiff file with 3 bands only.
    print ("Translating to tiff file.")
    beforeTranslateTime = time.time() - start
    ds = gdal.Translate("temp", ds, bandList = [1,2,3], scaleParams = scaleParams, exponents = [0.5, 0.5, 0.5], outputType = gdal.GDT_Byte, options = ["PHOTOMETRIC=RGB"], format = "MEM")
    afterTranslateTime = time.time() - start
    print ("Translate execution time: " + str(afterTranslateTime-beforeTranslateTime))

    #Create overlays
    print ("Generate overviews.")
    generic.executeOverviews(ds)

    print ("Save with overviews.")
    outputFilePath = outputDirectory + "/productOutput.tiff"
    gdal.Translate(outputFilePath, ds, format = 'GTiff')

    # now write the output json file, for EI Neo
    product = {
        "name": "True colour image",
        "productType": "COVERAGE",
        "SRS":"EPSG:4326",
        "envelopCoordinatesWKT": productFootprintWKT,
        "filePath": outputFilePath,
        "description": "True colour image from Kompsat-2 platform"
    }

    generic.writeOutput(outputDirectory, "True colour generation using geocento process", [product])

def main():
    return trueColour(sys.argv)

if __name__ == '__main__':
    sys.exit(trueColour(sys.argv))
