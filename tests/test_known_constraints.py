#!/usr/bin/env python

import numpy as np
import pytest
from olympus.campaigns import Campaign, ParameterSpace
from olympus.datasets import Dataset
from olympus.emulators import Emulator
from olympus.objects import (
    ParameterCategorical,
    ParameterContinuous,
    ParameterDiscrete,
    ParameterVector,
)
from olympus.scalarizers import Scalarizer
from olympus.surfaces import Surface

from atlas.planners.gp.planner import BoTorchPlanner


CONT = {
    "init_design_strategy": [
        "random",
    ],  # init design strategues
    "batch_size": [1],  # batch size
    "use_descriptors": [False],  # use descriptors
    "acquisition_optimizer": ['gradient', 'genetic'],
}

CAT = {
    "init_design_strategy": ["random"],
    "batch_size": [1],
    "use_descriptors": [False, True],
}


MIXED_CAT_DISC_CONT = {
    "init_design_strategy": ["random"],
    "batch_size": [1],
    "use_descriptors": [False, True],
}


@pytest.mark.parametrize("init_design_strategy", CONT["init_design_strategy"])
@pytest.mark.parametrize("batch_size", CONT["batch_size"])
@pytest.mark.parametrize("use_descriptors", CONT["use_descriptors"])
@pytest.mark.parametrize("acquisition_optimizer", CONT["acquisition_optimizer"])
def test_init_design_cont(init_design_strategy, batch_size, use_descriptors, acquisition_optimizer):
    run_continuous(init_design_strategy, batch_size, use_descriptors, acquisition_optimizer)


def known_constraints_cont(params):
    # for 3d unit hypercube param space
    if params[0] > 0.8 or params[2] > 0.9:
        return False
    if params[2] < 0.1 or params[1] < 0.1:
        return False
    return True

def known_constraints_cat(params):
    ''' for cat dejong '''
    blacklist1 = [f'x{i}' for i in np.arange(0, 16, 2)]
    blacklist2 = ['x20', 'x19', 'x10']
    if np.logical_or(
        params[0] in blacklist1,
        params[1] in blacklist2
    ):
        return False

    return True

def known_constraints_mixed_cat_disc(params):
    ''' custom param space '''
    # TODO: disc params need to be converted to float if with 
    if params[0] == 'x0' and float(params[1])>0.5:
        return False
    if params[0] == 'x3' and float(params[2])<0.25:
        return False

    return True


def known_constraints_fully_disc(params):
    ''' custom param space '''
    if float(params[0]) > 0.7 and float(params[2]< 0.25):
        return False
    if float(params[1]) == 0.5 and float(params[2]>0.5):
        return False
    return True


def known_constraint_mixed_cat_disc_large_space(param):
    """
    """
    surfactant0_type = param[0]
    surfactant0_conc = float(param[1])
    surfactant1_type = param[2]
    surfactant1_conc = float(param[3])
    surfactant2_type = param[4]
    surfactant2_conc = float(param[5])
    org_volume = float(param[6])

    surfactant_types = [surfactant0_type,surfactant1_type,surfactant2_type]
    surfactant_concs = [surfactant0_conc,surfactant1_conc,surfactant2_conc]

    # check that we dont have all null surfactant
    num_null = surfactant_types.count('null')
    if num_null == 3:
        return False

    # check that we have unique surfactants
    non_null_surfactant_types = list(filter(('null').__ne__, surfactant_types))
    unique_surfactants = list(np.unique(non_null_surfactant_types))

    # check for duplicated non-null surfactants
    if len(unique_surfactants) < len(surfactant_types)-num_null:
        return False

    # check that we dont have all null surfactant
    if all([s=='null' for s in surfactant_types]):
        return False

    for s, c in zip(surfactant_types,surfactant_concs):
        # if null, the concentration must be 0.
        if s == 'null':
            if not c == 0.:
                return False
        # if not null, the concentration must be > 0.
        else:
            if not c > 0.:
                return False
            
    # if not blacklist.empty:
    #     print('HERE!')
    #     quit()

    # if all checks pass, this is a feasible point
    return True


def run_continuous(
    init_design_strategy, batch_size, use_descriptors, acquisition_optimizer, num_init_design=5
):
    def surface(x):
        if np.random.uniform()<0.5:
            return np.sin(8 * x[0]) - 2 * np.cos(6 * x[1]) + np.exp(-2.0 * x[2])
        else:
            return np.nan

    param_space = ParameterSpace()
    param_0 = ParameterContinuous(name="param_0", low=0.0, high=1.0)
    param_1 = ParameterContinuous(name="param_1", low=0.0, high=1.0)
    param_2 = ParameterContinuous(name="param_2", low=0.0, high=1.0)
    param_space.add(param_0)
    param_space.add(param_1)
    param_space.add(param_2)

    planner = BoTorchPlanner(
        goal="minimize",
        feas_strategy="fwa",
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        batch_size=batch_size,
        acquisition_type='ei',
        #acquisition_optimizer_kind='genetic',
        acquisition_optimizer_kind=acquisition_optimizer,
        known_constraints=[known_constraints_cont],
    )

    planner.set_param_space(param_space)

    campaign = Campaign()
    campaign.set_param_space(param_space)

    BUDGET = num_init_design + batch_size * 4

    while len(campaign.observations.get_values()) < BUDGET:

        samples = planner.recommend(campaign.observations)
        for sample in samples:
            sample_arr = sample.to_array()
            measurement = surface(sample_arr)
            campaign.add_observation(sample_arr, measurement)

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET

    # check that all the measured values pass the known constraint
    meas_params = campaign.observations.get_params()

    for param in meas_params:
        print(param)
        for kc in planner.known_constraints:
            print(kc(param))

    kcs = [known_constraints_cont(param) for param in meas_params]
    print(kcs)
    assert all(kcs)


def run_discrete(
    init_design_strategy, batch_size, use_descriptors, num_init_design=5
):
    def surface(x):
        return np.sin(8 * x[0]) - 2 * np.cos(6 * x[1]) + np.exp(-2.0 * x[2])

    param_space = ParameterSpace()
    param_0 = ParameterDiscrete(
        name="param_0",
        options=[0.0, 0.1, 0.3, 0.5, 0.7, 0.9, 1.0],
    )
    param_1 = ParameterDiscrete(
        name="param_1",
        options=[0.0, 0.25, 0.5, 0.75, 1.0],
    )
    param_2 = ParameterDiscrete(
        name="param_2",
        options=[0.0, 0.25, 0.5, 0.75, 1.0],
    )
    param_space.add(param_0)
    param_space.add(param_1)
    param_space.add(param_2)

    planner = BoTorchPlanner(
        goal="minimize",
        feas_strategy="naive-0",
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        batch_size=batch_size,
        acquisition_optimizer='gradient',
        known_constraints=[known_constraints_fully_disc]
    )

    planner.set_param_space(param_space)

    campaign = Campaign()
    campaign.set_param_space(param_space)

    BUDGET = num_init_design + batch_size * 4

    while len(campaign.observations.get_values()) < BUDGET:

        samples = planner.recommend(campaign.observations)
        for sample in samples:
            sample_arr = sample.to_array()
            measurement = surface(sample_arr)
            campaign.add_observation(sample_arr, measurement)

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET

    # check that all the measured values pass the known constraint
    meas_params = campaign.observations.get_params()
    kcs = [known_constraints_fully_disc(param) for param in meas_params]
    assert all(kcs)


def run_categorical(
    init_design_strategy, batch_size, use_descriptors, num_init_design=5
):

    surface_kind = "CatDejong"
    surface = Surface(kind=surface_kind, param_dim=2, num_opts=21)

    campaign = Campaign()
    campaign.set_param_space(surface.param_space)

    planner = BoTorchPlanner(
        goal="minimize",
        feas_strategy="naive-0",
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        batch_size=batch_size,
        use_descriptors=use_descriptors,
        acquisition_optimizer_kind='gradient',
        known_constraints=[known_constraints_cat],
    )
    planner.set_param_space(surface.param_space)

    BUDGET = num_init_design + batch_size * 4

    while len(campaign.observations.get_values()) < BUDGET:

        samples = planner.recommend(campaign.observations)
        for sample in samples:
    
            sample_arr = sample.to_array()
            measurement = np.array(surface.run(sample_arr))
            # print(sample, measurement)
            campaign.add_observation(sample_arr, measurement[0])

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET

    # check that all the measured values pass the known constraint
    meas_params = campaign.observations.get_params()
    kcs = [known_constraints_cat(param) for param in meas_params]
    assert all(kcs)


def run_mixed_cat_disc(
    init_design_strategy, batch_size, use_descriptors, num_init_design=5,
):
    def surface(x):
        if x["param_0"] == "x0":
            factor = 0.1
        elif x["param_0"] == "x1":
            factor = 1.0
        elif x["param_0"] == "x2":
            factor = 10.0

        return (
            np.sin(8.0 * x["param_1"])
            - 2.0 * np.cos(6.0 * x["param_1"])
            + np.exp(-2.0 * x["param_2"])
            + 2.0 * (1.0 / factor)
        )

    if use_descriptors:
        desc_param_0 = [[float(i), float(i)] for i in range(3)]
    else:
        desc_param_0 = [None for i in range(3)]

    param_space = ParameterSpace()
    param_0 = ParameterCategorical(
        name="param_0",
        options=["x0", "x1", "x2"],
        descriptors=desc_param_0,
    )
    param_1 = ParameterDiscrete(
        name="param_1",
        options=[0.0, 0.25, 0.5, 0.75, 1.0],
    )
    param_2 = ParameterDiscrete(
        name="param_2",
        options=[0.0, 0.25, 0.5, 0.75, 1.0],
    )
    param_space.add(param_0)
    param_space.add(param_1)
    param_space.add(param_2)

    if batch_size>1:
        acquisition_type = 'qei'
    else:
        acquisition_type = 'ei'

    planner = BoTorchPlanner(
        goal="minimize",
        feas_strategy="naive-0",
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        batch_size=batch_size,
        use_descriptors=use_descriptors,
        acquisition_type=acquisition_type,
        acquisition_optimizer_kind='genetic',

        known_constraints=[known_constraints_mixed_cat_disc],
    )

    planner.set_param_space(param_space)

    campaign = Campaign()
    campaign.set_param_space(param_space)

    BUDGET = num_init_design + batch_size * 4 

    while len(campaign.observations.get_values()) < BUDGET:

        samples = planner.recommend(campaign.observations)
        print(samples)
        print('len(samples) : ', len(samples))
        for sample in samples:

            measurement = surface(sample)
            campaign.add_observation(sample, measurement)
    

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET

    # check that all the measured values pass the known constraint
    meas_params = campaign.observations.get_params()
    kcs = [known_constraints_mixed_cat_disc(param) for param in meas_params]
    assert all(kcs)


def run_mixed_cat_disc_cont(
    init_design_strategy, batch_size, use_descriptors, num_init_design=5
):
    def surface(x):
        if x["param_0"] == "x0":
            factor = 0.1
        elif x["param_0"] == "x1":
            factor = 1.0
        elif x["param_0"] == "x2":
            factor = 10.0

        return (
            np.sin(8.0 * x["param_1"])
            - 2.0 * np.cos(6.0 * x["param_1"])
            + np.exp(-2.0 * x["param_2"])
            + 2.0 * (1.0 / factor)
            + x["param_3"]
        )

    if use_descriptors:
        desc_param_0 = [[float(i), float(i)] for i in range(3)]
        print('here!')
    else:
        desc_param_0 = [None for i in range(3)]

    param_space = ParameterSpace()
    param_0 = ParameterCategorical(
        name="param_0",
        options=["x0", "x1", "x2"],
        descriptors=desc_param_0,
    )
    param_1 = ParameterDiscrete(
        name="param_1",
        options=[0.0, 0.25, 0.5, 0.75, 1.0],
    )
    param_2 = ParameterContinuous(
        name="param_2",
        low=0.0,
        high=1.0,
    )
    param_3 = ParameterContinuous(
        name="param_3",
        low=0.0,
        high=1.0,
    )
    param_space.add(param_0)
    param_space.add(param_1)
    param_space.add(param_2)
    param_space.add(param_3)

    planner = BoTorchPlanner(
        goal="minimize",
        feas_strategy="naive-0",
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        batch_size=batch_size,
        use_descriptors=use_descriptors,
        acquisition_optimizer_kind='gradient',
        # TODO: implement the known constraints for this
        #known_constraints=[]
        # acquisition_type='general',
        # general_parameters=[0],
    )

    planner.set_param_space(param_space)

    campaign = Campaign()
    campaign.set_param_space(param_space)

    BUDGET = num_init_design + batch_size * 5

    while len(campaign.observations.get_values()) < BUDGET:

        samples = planner.recommend(campaign.observations)
        for sample in samples:

            measurement = surface(sample)
            campaign.add_observation(sample, measurement)

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET

    # check that all the measured values pass the known constraint
    # meas_params = campaign.observations.get_params()
    # kcs = [known_constraints_cat_disc_cont(param) for param in meas_params]
    # assert all(kcs)


def run_mixed_cat_disc_large_space(init_design_strategy, batch_size, use_descriptors, num_init_design=5):
    '''
    '''

    surfactant_names = [
        'null', # no surfactant
        'tween_80', 
        'pluronic_f127',
        'tween_20'  
        'polyvinyl_alcohol',
        'sodium_dodecyl_sulfate',
        'pluronic_f68',
        'polyvinylpyrrolidone',
        'peg_10k',
    ]
    surfactant_descs = [None for _ in range(len(surfactant_names))]
    surfactant_conc_options = [0.0, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.07, 0.08, 0.09, 0.1] # % 
    org_volume_options = [10., 20., 30., 40., 50., 60., 70., 80., 90., 100.] # uL
    goals = ['max', 'min', 'max']

    # parameter space
    param_space = ParameterSpace()

    # surfactant 0 type
    param_space.add(
        ParameterCategorical(
            name='surfactant0_type',
            options=surfactant_names,
            descriptors=surfactant_descs,
        )
    )
    # surfactant 0 conc
    param_space.add(
        ParameterDiscrete(
            name='surfactant0_conc',
            options=surfactant_conc_options,
        )
    )
    # surfactant 1 type
    param_space.add(
        ParameterCategorical(
            name='surfactant1_type',
            options=surfactant_names,
            descriptors=surfactant_descs,
        )
    )
    # surfactant 1 conc
    param_space.add(
        ParameterDiscrete(
            name='surfactant1_conc',
            options=surfactant_conc_options,
        )
    )
    # surfactant 2 type
    param_space.add(
        ParameterCategorical(
            name='surfactant2_type',
            options=surfactant_names,
            descriptors=surfactant_descs,
        )
    )
    # surfactant 2 conc
    param_space.add(
        ParameterDiscrete(
            name='surfactant2_conc',
            options=surfactant_conc_options,
        )
    )

    # volume organic 
    # NOTE: volume aqueous = 2000uL -  volume organic
    param_space.add(
        ParameterDiscrete(
            name='org_volume',
            options=org_volume_options, # uL
        )
    )

    # value space
    value_space = ParameterSpace()
    value_space.add(ParameterContinuous(name='size'))  # particle size, nm
    value_space.add(ParameterContinuous(name='pdi')) # polydispersity index, a.u.
    value_space.add(ParameterContinuous(name='drug_amt')) # drug amount, ?? 

    campaign = Campaign()
    campaign.set_param_space(param_space)
    campaign.set_value_space(value_space)

    planner = BoTorchPlanner(
        goal='minimize', 
        batch_size=batch_size,
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        acquisition_type='qei',
        # batched_strategy='sequential',
        acquisition_optimizer_kind='gradient',
        known_constraints=[known_constraint_mixed_cat_disc_large_space],
        is_moo=True,
        scalarizer_kind='Hypervolume', 
        value_space=value_space,
        goals=goals,
    )
    planner.set_param_space(param_space)

    BUDGET = num_init_design + batch_size * 4 

    # beign optimization
    while len(campaign.observations.get_values()) < BUDGET:

        samples = planner.recommend(campaign.observations)
        print(samples)
        print('len(samples) : ', len(samples))
        for sample in samples:

            measurement = np.random.uniform(size=(3,))
            campaign.add_observation(sample, measurement)
    

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET

    # check that all the measured values pass the known constraint
    meas_params = campaign.observations.get_params()
    kcs = [known_constraints_mixed_cat_disc(param) for param in meas_params]
    assert all(kcs)



def run_compositional_constraint_cont(
    init_design_strategy, batch_size, num_init_design=5
):
    param_space = ParameterSpace()
    param_0 = ParameterContinuous(name="param_0", low=0.0, high=1.0)
    param_1 = ParameterContinuous(name="param_1", low=0.0, high=1.0)
    param_2 = ParameterContinuous(name="param_2", low=0.0, high=1.0)
    param_space.add(param_0)
    param_space.add(param_1)
    param_space.add(param_2)

    planner = BoTorchPlanner(
        goal="minimize",
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        batch_size=batch_size,
        acquisition_type='ei',
        acquisition_optimizer_kind='gradient',
        # all params must sum to 1. (simplex/compositional constraint)
        compositional_params=[0,1,2],
    )

    planner.set_param_space(param_space)

    campaign = Campaign()
    campaign.set_param_space(param_space)

    BUDGET = 12

    while len(campaign.observations.get_values()) < BUDGET:

        samples = planner.recommend(campaign.observations)
        for sample in samples:
            sample_arr = sample.to_array()
            measurement = np.random.uniform()
            campaign.add_observation(sample_arr, measurement)

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET

    # check that all the parameters sum to 1. 
    meas_params = campaign.observations.get_params()
    sums = [np.sum(param) for param in meas_params]
    assert all([sum_==1. for sum_ in sums])


def run_permutation_constraint_mixed_cat_disc(
    init_design_strategy, batch_size, num_init_design=5
):
    param_space = ParameterSpace()
    param_0 = ParameterDiscrete(
        name="param_0",
        options=[0.0, 0.25, 0.5, 0.75, 1.0],
    )
    param_1 = ParameterCategorical(
        name="param_1",
        options=["x0", "x1", "x2"],
        descriptors=[None, None, None],
    )
    param_2 = ParameterCategorical(
        name="param_2",
        options=["x0", "x1", "x2"],
        descriptors=[None, None, None],
    )
    param_3 = ParameterCategorical(
        name="param_3",
        options=["x0", "x1", "x2"],
        descriptors=[None, None, None],
    )
    param_space.add(param_0)
    param_space.add(param_1)
    param_space.add(param_2)
    param_space.add(param_3)

    planner = BoTorchPlanner(
        goal="minimize",
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        use_descriptors=False,
        batch_size=batch_size,
        acquisition_type='ei',
        acquisition_optimizer_kind='gradient',
        # permutation constraint on 3 categorical parameters
        permutation_params=[1,2,3],
    )

    planner.set_param_space(param_space)

    campaign = Campaign()
    campaign.set_param_space(param_space)

    BUDGET = 12

    while len(campaign.observations.get_values()) < BUDGET:

        samples = planner.recommend(campaign.observations)
        for sample in samples:
            sample_arr = sample.to_array()
            measurement = np.random.uniform()
            campaign.add_observation(sample_arr, measurement)

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET

    # validate permutation constraint
    meas_params = campaign.observations.get_params()
    vals = []
    for param in meas_params:
        val = []
        for idx in planner.known_constraints.permutation_params:
            if param_space[idx].type=='categorical':
                val.append(param_space[idx].options.index(param[idx]))
            else:
                val.append(float(param[idx]))
        vals.append(val)    
        
    assert all([val==sorted(val) for val in vals])

    

def run_pending_experiment_constraint_cat(init_design_strategy, batch_size, use_descriptors, num_init_design=5):
    surface_kind = "CatDejong"
    surface = Surface(kind=surface_kind, param_dim=2, num_opts=5)

    campaign = Campaign()
    campaign.set_param_space(surface.param_space)

    planner = BoTorchPlanner(
        goal="minimize",
        init_design_strategy=init_design_strategy,
        num_init_design=num_init_design,
        batch_size=batch_size,
        use_descriptors=use_descriptors,
        acquisition_optimizer_kind='gradient',
        known_constraints=[known_constraints_cat],
    )
    planner.set_param_space(surface.param_space)

    BUDGET = num_init_design + batch_size * 4

    while len(campaign.observations.get_values()) < BUDGET:

        if len(campaign.observations.get_values()) >= num_init_design:
            # TODO: only use the pending experiments after the initial design has completed
            pending_experiments = [
                { f'param_0': f'x{np.random.randint(5)}', 'param_1': f'x{np.random.randint(5)}'},
                { f'param_0': f'x{np.random.randint(5)}', 'param_1': f'x{np.random.randint(5)}'},
                { f'param_0': f'x{np.random.randint(5)}', 'param_1': f'x{np.random.randint(5)}'},
                { f'param_0': f'x{np.random.randint(5)}', 'param_1': f'x{np.random.randint(5)}'},
                { f'param_0': f'x{np.random.randint(5)}', 'param_1': f'x{np.random.randint(5)}'},
            ]
            pending_experiments = [
                ParameterVector().from_dict(pending_exp, surface.param_space) for pending_exp in pending_experiments
            ]

            #  set pending experiment constraint
            planner.set_pending_experiments(pending_experiments=pending_experiments)

            print('has pending experiment constriant : ', planner.known_constraints.has_pending_experiment_constraint)
            print(planner.known_constraints.known_constraints[-1])

        samples = planner.recommend(campaign.observations)
        for sample in samples:

            if len(campaign.observations.get_values()) >= num_init_design:
                # assert that the proposed sample in not in the list of pending experiments
                for pending_exp in pending_experiments:
                    sample_arr = sample.to_array()
                    pending_exp_arr = pending_exp.to_array().astype(str)
                    assert not (pending_exp_arr == sample_arr.astype(str)).all()
    
            sample_arr = sample.to_array()
            measurement = np.array(surface.run(sample_arr))
            # print(sample, measurement)
            campaign.add_observation(sample_arr, measurement[0])

    assert len(campaign.observations.get_params()) == BUDGET
    assert len(campaign.observations.get_values()) == BUDGET



if  __name__ == '__main__':
    #print(type(known_constraints_cont))
    #run_continuous('random',1,False, 'gradient',)
    #run_categorical('random',1,False )
    #run_mixed_cat_disc_cont('random',1,False)
    
    #run_mixed_cat_disc('random', 1, False)
    #run_mixed_cat_disc('random', 3, False)

    #run_discrete('random', 1, False)
    #run_discrete('random', 2, False)

    #run_mixed_cat_disc_large_space('random', 5, False)

    #run_compositional_constraint_cont('random', 1, num_init_design=5)

    #run_permutation_constraint_mixed_cat_disc('random', 1, num_init_design=5)

    run_pending_experiment_constraint_cat('random', 1, False )