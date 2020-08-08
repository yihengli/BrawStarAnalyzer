clean: clean-pyc
	conda remove --name mfe_workshop --all --yes || echo
	echo Run "source deactivate" to exit from the conda environment

clean-pyc: ## removes pyc files from your local directory
	find . -name '*.pyc' -exec rm -f {} \;
	find . -name '*.pyo' -exec rm -f {} \;

install:
	conda create --name bsa --channel conda-forge --file conda-requirements.txt --yes
	source activate bsa && \
	pip install -r requirements.txt

test:
	pytest src/production_code
